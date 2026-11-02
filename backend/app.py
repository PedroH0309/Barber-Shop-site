"""Precision Agenda — standalone single-barber scheduling API.
Run from project root with: uvicorn backend.app:app --reload
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
DATA = Path(os.environ.get('AGENDA_DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
UPLOADS = DATA / 'uploads'
UPLOADS.mkdir(exist_ok=True)
DB = DATA / 'agenda.sqlite3'
TZ = ZoneInfo('America/Sao_Paulo')
COOKIE = 'precision_admin_session'
SECURE_COOKIE = os.environ.get('COOKIE_SECURE', '0') == '1'
GRAPH_VERSION = os.environ.get('META_GRAPH_VERSION', 'v23.0')


def now():
    return datetime.now(TZ)


def utc_iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def booking_datetime(day: str, hour: str) -> datetime:
    try:
        d = datetime.fromisoformat(day + 'T' + hour).replace(tzinfo=TZ)
        if d.strftime('%Y-%m-%d') != day or d.strftime('%H:%M') != hour:
            raise ValueError()
        return d
    except ValueError:
        raise HTTPException(422, 'Data ou horário inválido')


@contextmanager
def connection():
    conn = sqlite3.connect(DB, timeout=8, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 8000')
    try:
        yield conn
    finally:
        conn.close()


def setting(conn, key, default=''):
    row = conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return row['value'] if row else default


def init_db():
    with connection() as db:
        db.execute('PRAGMA journal_mode = WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin(id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL UNIQUE, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,csrf_token TEXT NOT NULL,expires_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',price_cents INTEGER NOT NULL CHECK(price_cents>=0),duration_min INTEGER NOT NULL CHECK(duration_min BETWEEN 10 AND 360),image TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',price_cents INTEGER NOT NULL CHECK(price_cents>=0),period TEXT NOT NULL DEFAULT 'mensal',benefits TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY AUTOINCREMENT,weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),start TEXT NOT NULL,end TEXT NOT NULL, CHECK(start<end));
        CREATE TABLE IF NOT EXISTS blocks(id INTEGER PRIMARY KEY AUTOINCREMENT,day TEXT NOT NULL,start TEXT NOT NULL DEFAULT '00:00',end TEXT NOT NULL DEFAULT '23:59',reason TEXT NOT NULL DEFAULT '', CHECK(start<end));
        CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY AUTOINCREMENT,public_token TEXT UNIQUE NOT NULL,service_id INTEGER NOT NULL REFERENCES services(id),service_name TEXT NOT NULL,price_cents INTEGER NOT NULL,duration_min INTEGER NOT NULL,customer_name TEXT NOT NULL,customer_phone TEXT NOT NULL,start_at TEXT NOT NULL,end_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pendente',consent_whatsapp INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,reminder_state TEXT NOT NULL DEFAULT 'pending',reminder_attempts INTEGER NOT NULL DEFAULT 0,reminder_updated TEXT NOT NULL DEFAULT '',reminder_error TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS idx_booking_start ON bookings(start_at,end_at,status);
        CREATE TABLE IF NOT EXISTS booking_events(id INTEGER PRIMARY KEY AUTOINCREMENT,booking_id INTEGER NOT NULL REFERENCES bookings(id),old_status TEXT NOT NULL,new_status TEXT NOT NULL,actor TEXT NOT NULL,occurred_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_booking_events ON booking_events(booking_id,occurred_at);
        ''')
        # Legacy system considered 'agendado' a confirmed reservation. Preserve that meaning.
        # New reservations explicitly start in 'pendente' and block availability until decided.
        db.execute("UPDATE bookings SET status='aprovado' WHERE status='agendado'")
        defaults = {
          'business_name':'Precision Barber Studio','address':'','whatsapp':'',
          'published':'0','lead_hours':'1','advance_days':'45','slot_step':'30',
          'calendar_token':secrets.token_urlsafe(32), 'reminder_hours':'3',
        }
        for k,v in defaults.items():
            db.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
        if not db.execute('SELECT 1 FROM services LIMIT 1').fetchone():
            for x in [
               ('Corte masculino','Corte clássico ou moderno com acabamento detalhado.',4500,45,'/assets/section-standard.jpg'),
               ('Degradê / Fade','Transição precisa e acabamento personalizado.',5000,45,'/assets/section-standard.jpg'),
               ('Barba & design','Alinhamento, desenho e cuidado da barba.',3500,30,'/assets/hero-poster.jpg'),
               ('Corte + Barba','Experiência completa de cabelo e barba.',7500,75,'/assets/hero-ending.jpg')]:
                db.execute('INSERT INTO services(name,description,price_cents,duration_min,image) VALUES(?,?,?,?,?)',x)
        # Seed only once: an intentionally empty timetable must remain empty after restart.
        if not db.execute("SELECT 1 FROM settings WHERE key='shifts_initialized'").fetchone():
            is_empty = not db.execute('SELECT 1 FROM shifts LIMIT 1').fetchone()
            if is_empty:
                for wd in range(1,6):
                    db.execute('INSERT INTO shifts(weekday,start,end) VALUES(?,?,?)',(wd,'09:00','12:00'))
                    db.execute('INSERT INTO shifts(weekday,start,end) VALUES(?,?,?)',(wd,'13:00','19:00'))
            db.execute("INSERT INTO settings(key,value) VALUES('shifts_initialized','1')")


def money(cents):
    return round(cents/100, 2)


def service_json(row):
    return {'id':row['id'],'name':row['name'],'description':row['description'],'price':money(row['price_cents']),
      'price_cents':row['price_cents'],'duration_min':row['duration_min'],'image':row['image'],'active':bool(row['active'])}


def plan_json(row):
    return {'id':row['id'],'name':row['name'],'description':row['description'],'price':money(row['price_cents']),
      'price_cents':row['price_cents'],'period':row['period'],'benefits':row['benefits'],'active':bool(row['active'])}


def book_json(row, admin=False):
    x = {'id':row['id'] if admin else None,'service':row['service_name'], 'price':money(row['price_cents']),
         'duration_min':row['duration_min'],'start':row['start_at'],'end':row['end_at'],'status':row['status']}
    if admin:
        x.update({'name':row['customer_name'],'phone':row['customer_phone'], 'service_id':row['service_id'],
            'consent_whatsapp':bool(row['consent_whatsapp']),'reminder_state':row['reminder_state'],
            'reminder_error':row['reminder_error'],'created_at':row['created_at']})
    return x


def valid_phone(raw):
    digits = re.sub(r'\D','',raw or '')
    if digits.startswith('55') and len(digits) in (12,13):
        digits = digits[2:]
    if len(digits) not in (10,11) or digits[0]=='0' or digits[1]=='0':
        raise HTTPException(422,'Informe um telefone com DDD válido')
    return '55'+digits


def slots_for(db, day, service, ignore_booking=None):
    try:
        current_day = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(422,'Data inválida')
    if (current_day-now().date()).days < 0 or (current_day-now().date()).days > int(setting(db,'advance_days','45')):
        return []
    # Public calendar + admin schedule use Sunday=0, Monday=1, ..., Saturday=6.
    # datetime.date.weekday() uses Monday=0, so convert without rewriting saved shifts.
    public_weekday = (current_day.weekday() + 1) % 7
    shifts = db.execute('SELECT start,end FROM shifts WHERE weekday=? ORDER BY start',(public_weekday,)).fetchall()
    blocks = db.execute('SELECT start,end FROM blocks WHERE day=?',(day,)).fetchall()
    busy = db.execute("SELECT id,start_at,end_at FROM bookings WHERE substr(start_at,1,10)=? AND status IN ('pendente','aprovado','confirmado')",(day,)).fetchall()
    step = int(setting(db,'slot_step','30'))
    lead = int(setting(db,'lead_hours','1'))
    available=[]
    for shift in shifts:
        t = booking_datetime(day, shift['start'])
        stop = booking_datetime(day, shift['end'])
        while t+timedelta(minutes=service['duration_min']) <= stop:
            e = t+timedelta(minutes=service['duration_min'])
            tstr=t.strftime('%H:%M')
            estr=e.strftime('%H:%M')
            if t > now()+timedelta(hours=lead) and not any(tstr < b['end'] and estr > b['start'] for b in blocks) and not any(t.isoformat(timespec='minutes') < b['end_at'] and e.isoformat(timespec='minutes') > b['start_at'] for b in busy if b['id']!=ignore_booking):
                available.append(tstr)
            t += timedelta(minutes=step)
    return sorted(set(available))


def require_admin(request:Request):
    token = request.cookies.get(COOKIE,'')
    if not token:
        raise HTTPException(401,'Acesso restrito ao administrador')
    digest = hashlib.sha256(token.encode()).hexdigest()
    with connection() as db:
        s=db.execute('SELECT * FROM sessions WHERE token_hash=? AND expires_at>?',(digest,int(time.time()))).fetchone()
    if not s:
        raise HTTPException(401,'Sessão expirada. Entre novamente.')
    return s


def require_write(request):
    session=require_admin(request)
    provided=request.headers.get('x-csrf-token','')
    if not provided or not secrets.compare_digest(provided,session['csrf_token']):
        raise HTTPException(403,'Token de segurança inválido')
    return session


def make_hash(password,salt):
    return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=2**14,r=8,p=1).hex()


class BookingCreate(BaseModel):
    service_id:int
    day:str
    time:str
    name:str=Field(min_length=5,max_length=100)
    phone:str=Field(min_length=10,max_length=30)
    consent_whatsapp:bool=False

class Login(BaseModel):
    username:str
    password:str

class CredentialsIn(BaseModel):
    username:str=Field(min_length=3,max_length=40)
    current_password:str
    new_password:str=Field(min_length=12,max_length=256)

class ServiceIn(BaseModel):
    name:str=Field(min_length=2,max_length=90)
    description:str=Field(default='',max_length=300)
    price_cents:int=Field(ge=0,le=1000000)
    duration_min:int=Field(ge=10,le=360)
    active:bool=True

class PlanIn(BaseModel):
    name:str=Field(min_length=2,max_length=90)
    description:str=Field(default='',max_length=300)
    price_cents:int=Field(ge=0,le=10000000)
    period:str=Field(default='mensal',max_length=40)
    benefits:str=Field(default='',max_length=700)
    active:bool=True

class ShiftIn(BaseModel):
    weekday:int=Field(ge=0,le=6)
    start:str
    end:str

class BlockIn(BaseModel):
    day:str
    start:str='00:00'
    end:str='23:59'
    reason:str=Field(default='',max_length=150)

class BusinessIn(BaseModel):
    business_name:str=Field(min_length=2,max_length=100)
    address:str=Field(default='',max_length=220)
    whatsapp:str=Field(default='',max_length=30)
    published:bool=False
    lead_hours:int=Field(default=1,ge=0,le=72)
    advance_days:int=Field(default=45,ge=1,le=365)
    reminder_hours:int=Field(default=3,ge=1,le=24)

class StatusIn(BaseModel):
    status:str


@asynccontextmanager
async def lifespan(app):
    init_db()
    worker=None
    if os.environ.get('REMINDERS_ENABLED')=='1':
        worker=asyncio.create_task(reminder_loop())
    try:
        yield
    finally:
        if worker:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass

app=FastAPI(title='Precision Agenda',docs_url=None,redoc_url=None,lifespan=lifespan)

@app.middleware('http')
async def protect(request:Request,call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    if request.url.path.startswith('/api/') or request.url.path in ('/admin', '/admin.html', '/admin.js', '/admin.css', '/admin-mobile.css', '/admin-pwa.js', '/admin-sw.js'):
        response.headers['Cache-Control']='no-store'
    return response

@app.get('/api/public/config')
def get_public_config():
    with connection() as db:
        return {'business_name':setting(db,'business_name'),'address':setting(db,'address'),
            'published':setting(db,'published')=='1','advance_days':int(setting(db,'advance_days','45')),
            'services':[service_json(x) for x in db.execute('SELECT * FROM services WHERE active=1 ORDER BY id')],
            'plans':[plan_json(x) for x in db.execute('SELECT * FROM plans WHERE active=1 ORDER BY id')]}

@app.get('/api/public/slots')
def get_slots(service_id:int, day:str):
    with connection() as db:
        s=db.execute('SELECT * FROM services WHERE id=? AND active=1',(service_id,)).fetchone()
        if not s: raise HTTPException(404,'Serviço indisponível')
        return {'day':day,'slots':slots_for(db,day,s) if setting(db,'published')=='1' else [],'published':setting(db,'published')=='1'}

booking_rate={}
login_attempts={}
@app.post('/api/public/bookings',status_code=201)
def create_booking(payload:BookingCreate, request:Request):
    # In-memory basic throttle; configure a gateway limiter for public deployments.
    ip=request.client.host if request.client else 'unknown'
    key=(ip, re.sub(r'\D','',payload.phone))
    recent=[x for x in booking_rate.get(key,[]) if x>time.time()-3600]
    if len(recent)>=10: raise HTTPException(429,'Limite temporário de solicitações atingido')
    name=' '.join(payload.name.split())
    if len(name)<5 or len(name.split())<2: raise HTTPException(422,'Informe nome e sobrenome')
    phone=valid_phone(payload.phone)
    with connection() as db:
        try:
            db.execute('BEGIN IMMEDIATE')
            if setting(db,'published')!='1': raise HTTPException(503,'Agenda em configuração. Tente novamente mais tarde.')
            s=db.execute('SELECT * FROM services WHERE id=? AND active=1',(payload.service_id,)).fetchone()
            if not s: raise HTTPException(404,'Serviço indisponível')
            if payload.time not in slots_for(db,payload.day,s):
                raise HTTPException(409,'Este horário não está mais disponível. Escolha outro.')
            starts=booking_datetime(payload.day,payload.time)
            end=starts+timedelta(minutes=s['duration_min'])
            token=secrets.token_urlsafe(24)
            db.execute('''INSERT INTO bookings(public_token,service_id,service_name,price_cents,duration_min,customer_name,customer_phone,start_at,end_at,status,consent_whatsapp,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,'pendente',?,?)''', (token,s['id'],s['name'],s['price_cents'],s['duration_min'],name,phone,
                starts.isoformat(timespec='minutes'),end.isoformat(timespec='minutes'),int(payload.consent_whatsapp),now().isoformat(timespec='seconds')))
            db.commit()
        except Exception:
            db.rollback()
            raise
    booking_rate[key]=recent+[time.time()]
    return {'token':token,'service':s['name'],'price':money(s['price_cents']),
        'start':starts.isoformat(timespec='minutes'),'end':end.isoformat(timespec='minutes'),'status':'pendente',
        'message':'Solicitação recebida. Aguarde a aprovação do barbeiro; este horário está bloqueado até a decisão.'}


def google_calendar_url(starts,ends,service):
    with connection() as db:
        title=setting(db,'business_name')
        address=setting(db,'address')
    query=urlencode({'action':'TEMPLATE','text':f'{service} — {title}','dates':f'{utc_iso(starts)}/{utc_iso(ends)}',
        'details':'Agendamento realizado pela agenda online.','location':address})
    return 'https://calendar.google.com/calendar/render?'+query


def ics_escape(v):
    return str(v).replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')


def ics_event(b, business, address, admin=False):
    st=datetime.fromisoformat(b['start_at'])
    en=datetime.fromisoformat(b['end_at'])
    title=f"{b['service_name']} — {business}"
    if admin: title=f"{b['customer_name']} — {b['service_name']}"
    return ['BEGIN:VEVENT',f'UID:precision-{b["id"]}@agenda.local',f'DTSTAMP:{utc_iso(now())}',
     f'DTSTART:{utc_iso(st)}',f'DTEND:{utc_iso(en)}',f'SUMMARY:{ics_escape(title)}',
     f'DESCRIPTION:{ics_escape("Agendado pelo Precision Agenda")}',f'LOCATION:{ics_escape(address)}',
     'STATUS:CONFIRMED' if b['status']!='cancelado' else 'STATUS:CANCELLED','END:VEVENT']


def ics_response(lines):
    # RFC5545 uses CRLF; Unicode is fine with UTF-8 and short standard lines.
    return Response('\r\n'.join(lines)+'\r\n',media_type='text/calendar; charset=utf-8',
        headers={'Content-Disposition':'attachment; filename="agendamento.ics"','Cache-Control':'no-store'})

@app.get('/api/public/bookings/{token}')
def public_booking_status(token:str):
    # O token é uma credencial sigilosa; não exponha nome, telefone nem dados dos demais clientes.
    if len(token)>100: raise HTTPException(404,'Solicitação não encontrada')
    with connection() as db:
        b=db.execute('SELECT * FROM bookings WHERE public_token=?',(token,)).fetchone()
        if not b: raise HTTPException(404,'Solicitação não encontrada')
        approved=b['status'] in ('aprovado','confirmado','concluido')
        result={'status':b['status'],'service':b['service_name'],'price':money(b['price_cents']),
                'duration_min':b['duration_min'],'start':b['start_at'],'end':b['end_at'],
                'can_add_calendar':approved}
        if approved:
            result['google_url']=google_calendar_url(datetime.fromisoformat(b['start_at']),datetime.fromisoformat(b['end_at']),b['service_name'])
            result['ics_url']='/api/public/bookings/'+token+'/ics'
        return result

@app.get('/api/public/bookings/{token}/ics')
def booking_ics(token:str):
    with connection() as db:
        b=db.execute('SELECT * FROM bookings WHERE public_token=?',(token,)).fetchone()
        if not b: raise HTTPException(404,'Agendamento não encontrado')
        if b['status'] not in ('aprovado','confirmado','concluido'):
            raise HTTPException(409,'A exportação do calendário só fica disponível após a aprovação do barbeiro')
        return ics_response(['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Precision Agenda//PT-BR//EN','CALSCALE:GREGORIAN',
            'METHOD:PUBLISH',*ics_event(b,setting(db,'business_name'),setting(db,'address')),'END:VCALENDAR'])

@app.post('/api/admin/login')
def admin_login(data:Login,response:Response,request:Request):
    ip=request.client.host if request.client else 'unknown'
    recent=[t for t in login_attempts.get(ip,[]) if t>time.time()-900]
    if len(recent)>=12:
        raise HTTPException(429,'Muitas tentativas de acesso. Tente novamente mais tarde.')
    with connection() as db:
        row=db.execute('SELECT * FROM admin WHERE id=1').fetchone()
        if not row: raise HTTPException(503,'Administrador ainda não configurado. Execute o comando de instalação.')
        # Fixed-cost verification even for wrong username to reduce timing leaks.
        expected=make_hash(data.password,row['salt'])
        if data.username!=row['username'] or not hmac.compare_digest(expected,row['password_hash']):
            login_attempts[ip]=recent+[time.time()]
            time.sleep(.35)
            raise HTTPException(401,'Usuário ou senha inválidos')
        login_attempts.pop(ip,None)
        token=secrets.token_urlsafe(36); csrf=secrets.token_urlsafe(28)
        db.execute('DELETE FROM sessions WHERE expires_at<?',(int(time.time()),))
        db.execute('INSERT INTO sessions(token_hash,csrf_token,expires_at) VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),csrf,int(time.time())+7*86400))
    response.set_cookie(COOKIE,token,httponly=True,secure=SECURE_COOKIE,samesite='lax',max_age=7*86400,path='/')
    return {'ok':True,'csrf':csrf}

@app.get('/api/admin/me')
def admin_me(request:Request):
    session=require_admin(request)
    with connection() as db:
        admin=db.execute('SELECT username FROM admin WHERE id=1').fetchone()
    return {'authenticated':True,'csrf':session['csrf_token'], 'username':admin['username'] if admin else ''}

@app.post('/api/admin/logout')
def admin_logout(request:Request,response:Response):
    require_write(request)
    tok=request.cookies.get(COOKIE,'')
    with connection() as db: db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(tok.encode()).hexdigest(),))
    response.delete_cookie(COOKIE,path='/')
    return {'ok':True}

@app.put('/api/admin/credentials')
def change_credentials(data:CredentialsIn,request:Request,response:Response):
    session=require_write(request)
    username=data.username.strip()
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{3,40}',username):
        raise HTTPException(422,'Usuário deve ter 3 a 40 caracteres: letras, números, ponto, hífen ou sublinhado')
    if data.new_password == data.current_password:
        raise HTTPException(422,'Escolha uma senha nova, diferente da atual')
    with connection() as db:
        try:
            db.execute('BEGIN IMMEDIATE')
            admin=db.execute('SELECT * FROM admin WHERE id=1').fetchone()
            if not admin or not hmac.compare_digest(make_hash(data.current_password,admin['salt']),admin['password_hash']):
                raise HTTPException(403,'Senha atual incorreta')
            salt=secrets.token_hex(16)
            db.execute('UPDATE admin SET username=?,salt=?,password_hash=? WHERE id=1',
                (username,salt,make_hash(data.new_password,salt)))
            # Remove all sessions, including the current browser: credentials have changed.
            db.execute('DELETE FROM sessions')
            db.commit()
        except Exception:
            db.rollback()
            raise
    response.delete_cookie(COOKIE,path='/')
    return {'ok':True,'message':'Credenciais alteradas. Entre novamente com o novo usuário e senha.'}

@app.get('/api/admin/bookings/{id}/history')
def admin_booking_history(id:int,request:Request):
    require_admin(request)
    with connection() as db:
        booking=db.execute('SELECT * FROM bookings WHERE id=?',(id,)).fetchone()
        if not booking: raise HTTPException(404,'Agendamento não encontrado')
        events=db.execute('SELECT old_status,new_status,actor,occurred_at FROM booking_events WHERE booking_id=? ORDER BY id',(id,)).fetchall()
    return {'booking':book_json(booking,True),'events':[dict(event) for event in events]}

@app.get('/api/admin/overview')
def overview(request:Request,day:str|None=None):
    require_admin(request)
    day=day or now().date().isoformat()
    with connection() as db:
        all_books=db.execute('SELECT * FROM bookings WHERE substr(start_at,1,10)=? ORDER BY start_at',(day,)).fetchall()
        return {'date':day,'bookings':[book_json(x,True) for x in all_books],
          'all_future':db.execute("SELECT count(*) c FROM bookings WHERE start_at>=? AND status IN ('pendente','aprovado','confirmado')",(now().isoformat(timespec='minutes'),)).fetchone()['c'],
          'day_count':len([x for x in all_books if x['status'] in ('pendente','aprovado','confirmado','concluido')]),
          'pending_count':db.execute("SELECT count(*) c FROM bookings WHERE status='pendente' AND start_at>=?",(now().isoformat(timespec='minutes'),)).fetchone()['c'],
          'day_revenue':money(sum(x['price_cents'] for x in all_books if x['status'] in ('aprovado','confirmado','concluido')))}

@app.get('/api/admin/pending')
def admin_pending(request:Request):
    require_admin(request)
    with connection() as db:
        rows=db.execute("SELECT * FROM bookings WHERE status='pendente' AND start_at>=? ORDER BY start_at LIMIT 100",
                        (now().isoformat(timespec='minutes'),)).fetchall()
        return {'bookings':[book_json(x,True) for x in rows]}

@app.get('/api/admin/clients')
def admin_clients(request:Request):
    require_admin(request)
    # Build directory from existing reservations; no second copy of customer PII.
    with connection() as db:
        rows=db.execute('SELECT customer_name,customer_phone,service_name,status,start_at,created_at,id FROM bookings ORDER BY created_at DESC,id DESC').fetchall()
    clients={}
    current_time=now().isoformat(timespec='minutes')
    for b in rows:
        key=b['customer_phone']
        if key not in clients:
            clients[key]={'name':b['customer_name'],'phone':key,'reservations':0,'completed':0,
                          'future':0,'last_service':None,'next_service':None,'last_booking':None}
        c=clients[key]
        c['reservations']+=1
        if b['status']=='concluido':
            c['completed']+=1
            if not c['last_service'] or b['start_at']>c['last_service']:
                c['last_service']=b['start_at']
        if b['status'] in ('pendente','aprovado','confirmado') and b['start_at']>=current_time:
            c['future']+=1
            if not c['next_service'] or b['start_at']<c['next_service']:
                c['next_service']=b['start_at']
        if not c['last_booking'] or b['start_at']>c['last_booking']:
            c['last_booking']=b['start_at']
    result=sorted(clients.values(),key=lambda c:(c['last_booking'] or ''),reverse=True)
    return {'clients':result,'total':len(result),
        'returning':sum(1 for c in result if c['completed']>=2),
        'attendances':sum(c['completed'] for c in result)}

@app.get('/api/admin/bookings')
def admin_bookings(request:Request,from_date:str|None=None,to_date:str|None=None):
    require_admin(request)
    from_date=from_date or now().date().isoformat()
    to_date=to_date or (now().date()+timedelta(days=30)).isoformat()
    with connection() as db:
        return {'bookings':[book_json(x,True) for x in db.execute('SELECT * FROM bookings WHERE substr(start_at,1,10) BETWEEN ? AND ? ORDER BY start_at',(from_date,to_date))]}

# Transições explícitas: cliente não aprova sua própria reserva; somente o painel decide.
ALLOWED_TRANSITIONS={
 'pendente':{'aprovado','recusado','cancelado'},
 'aprovado':{'confirmado','cancelado','concluido','nao_compareceu'},
 'confirmado':{'cancelado','concluido','nao_compareceu'},
 'recusado':set(), 'cancelado':set(), 'concluido':set(), 'nao_compareceu':set()
}

@app.patch('/api/admin/bookings/{id}')
def update_booking_status(id:int,data:StatusIn,request:Request):
    require_write(request)
    with connection() as db:
        try:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM bookings WHERE id=?',(id,)).fetchone()
            if not old: raise HTTPException(404,'Solicitação não encontrada')
            old_status=old['status']
            if data.status==old_status:
                db.commit()
                return {'ok':True,'status':old_status}
            if data.status not in ALLOWED_TRANSITIONS.get(old_status,set()):
                raise HTTPException(409,'Mudança de status não permitida. Revise o estado atual da solicitação.')
            if data.status in ('aprovado','confirmado'):
                conflict=db.execute("SELECT 1 FROM bookings WHERE id<>? AND status IN ('pendente','aprovado','confirmado') AND start_at<? AND end_at>? LIMIT 1",
                    (id,old['end_at'],old['start_at'])).fetchone()
                if conflict: raise HTTPException(409,'Horário já está ocupado')
            db.execute('UPDATE bookings SET status=? WHERE id=?',(data.status,id))
            db.execute('INSERT INTO booking_events(booking_id,old_status,new_status,actor,occurred_at) VALUES(?,?,?,?,?)',
                       (id,old_status,data.status,'barbeiro',now().isoformat(timespec='seconds')))
            db.commit()
            return {'ok':True,'status':data.status}
        except Exception:
            db.rollback()
            raise

@app.get('/api/admin/services')
def admin_services(request:Request):
    require_admin(request)
    with connection() as db:return {'services':[service_json(x) for x in db.execute('SELECT * FROM services ORDER BY id')]}

@app.post('/api/admin/services')
def add_service(data:ServiceIn,request:Request):
    require_write(request)
    with connection() as db:
        cur=db.execute('INSERT INTO services(name,description,price_cents,duration_min,active) VALUES(?,?,?,?,?)',
            (data.name.strip(),data.description.strip(),data.price_cents,data.duration_min,int(data.active)))
        return {'id':cur.lastrowid}

@app.put('/api/admin/services/{id}')
def edit_service(id:int,data:ServiceIn,request:Request):
    require_write(request)
    with connection() as db:
        cur=db.execute('UPDATE services SET name=?,description=?,price_cents=?,duration_min=?,active=? WHERE id=?',
            (data.name.strip(),data.description.strip(),data.price_cents,data.duration_min,int(data.active),id))
        if not cur.rowcount: raise HTTPException(404,'Serviço não encontrado')
    return {'ok':True}

@app.delete('/api/admin/services/{id}')
def hide_service(id:int,request:Request):
    require_write(request)
    with connection() as db:
        if not db.execute('UPDATE services SET active=0 WHERE id=?',(id,)).rowcount: raise HTTPException(404,'Serviço não encontrado')
    return {'ok':True}

@app.post('/api/admin/services/{id}/photo')
async def service_photo(id:int,request:Request,image:UploadFile=File(...)):
    require_write(request)
    content=await image.read(5*1024*1024+1)
    if len(content)>5*1024*1024: raise HTTPException(413,'Imagem deve ter no máximo 5 MB')
    try:
        img=Image.open(io.BytesIO(content))
        img.verify()
        img=Image.open(io.BytesIO(content))
        if img.width*img.height>18_000_000: raise ValueError('Imagem muito grande')
        img=img.convert('RGB')
        img.thumbnail((1500,1500))
        out=UPLOADS/f'{uuid.uuid4().hex}.webp'
        img.save(out,'WEBP',quality=82,method=4)
    except (UnidentifiedImageError,ValueError,OSError):
        raise HTTPException(422,'Envie uma imagem JPEG, PNG ou WebP válida')
    with connection() as db:
        current=db.execute('SELECT 1 FROM services WHERE id=?',(id,)).fetchone()
        if not current:
            out.unlink(missing_ok=True)
            raise HTTPException(404,'Serviço não encontrado')
        db.execute('UPDATE services SET image=? WHERE id=?',('/uploads/'+out.name,id))
    return {'image':'/uploads/'+out.name}

@app.get('/api/admin/plans')
def admin_plans(request:Request):
    require_admin(request)
    with connection() as db:return {'plans':[plan_json(x) for x in db.execute('SELECT * FROM plans ORDER BY id')]}

@app.post('/api/admin/plans')
def add_plan(data:PlanIn,request:Request):
    require_write(request)
    with connection() as db:
        cur=db.execute('INSERT INTO plans(name,description,price_cents,period,benefits,active) VALUES(?,?,?,?,?,?)',
         (data.name,data.description,data.price_cents,data.period,data.benefits,int(data.active)))
        return {'id':cur.lastrowid}

@app.put('/api/admin/plans/{id}')
def edit_plan(id:int,data:PlanIn,request:Request):
    require_write(request)
    with connection() as db:
        cur=db.execute('UPDATE plans SET name=?,description=?,price_cents=?,period=?,benefits=?,active=? WHERE id=?',
         (data.name,data.description,data.price_cents,data.period,data.benefits,int(data.active),id))
        if not cur.rowcount: raise HTTPException(404,'Plano não encontrado')
    return {'ok':True}

@app.delete('/api/admin/plans/{id}')
def hide_plan(id:int,request:Request):
    require_write(request)
    with connection() as db:
        if not db.execute('UPDATE plans SET active=0 WHERE id=?',(id,)).rowcount: raise HTTPException(404,'Plano não encontrado')
    return {'ok':True}

@app.get('/api/admin/schedule')
def admin_schedule(request:Request):
    require_admin(request)
    with connection() as db:
        return {'shifts':[dict(x) for x in db.execute('SELECT * FROM shifts ORDER BY weekday,start')],
            'published':setting(db,'published')=='1',
            'blocks':[dict(x) for x in db.execute('SELECT * FROM blocks WHERE day>=? ORDER BY day,start',(now().date().isoformat(),))]}

def validate_shift_time(start:str,end:str):
    if not re.fullmatch(r'\d\d:\d\d',start) or not re.fullmatch(r'\d\d:\d\d',end) or start >= end:
        raise HTTPException(422,'Horário inválido')
    for hour in (start,end):
        try: datetime.strptime(hour,'%H:%M')
        except ValueError: raise HTTPException(422,'Horário inválido')


@app.post('/api/admin/shifts')
def add_shift(data:ShiftIn,request:Request):
    require_write(request)
    validate_shift_time(data.start,data.end)
    with connection() as db:
        overlap=db.execute('SELECT 1 FROM shifts WHERE weekday=? AND start<? AND end>?',(data.weekday,data.end,data.start)).fetchone()
        if overlap: raise HTTPException(409,'Este expediente se sobrepõe a outro')
        cur=db.execute('INSERT INTO shifts(weekday,start,end) VALUES(?,?,?)',(data.weekday,data.start,data.end))
    return {'id':cur.lastrowid}

@app.put('/api/admin/shifts/day/{weekday}')
def replace_weekday_shifts(weekday:int,data:ShiftIn,request:Request):
    """Replace all weekly shifts for a weekday with a single continuous shift."""
    require_write(request)
    if not 0 <= weekday <= 6 or data.weekday != weekday:
        raise HTTPException(422,'Dia da semana inválido')
    validate_shift_time(data.start,data.end)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM shifts WHERE weekday=?',(weekday,))
        db.execute('INSERT INTO shifts(weekday,start,end) VALUES(?,?,?)',(weekday,data.start,data.end))
        db.commit()
    return {'ok':True}

@app.delete('/api/admin/shifts/day/{weekday}')
def close_weekday(weekday:int,request:Request):
    require_write(request)
    if not 0 <= weekday <= 6: raise HTTPException(422,'Dia da semana inválido')
    with connection() as db:
        db.execute('DELETE FROM shifts WHERE weekday=?',(weekday,))
    return {'ok':True}

@app.delete('/api/admin/shifts/{id}')
def remove_shift(id:int,request:Request):
    require_write(request)
    with connection() as db: db.execute('DELETE FROM shifts WHERE id=?',(id,))
    return {'ok':True}

@app.post('/api/admin/blocks')
def add_block(data:BlockIn,request:Request):
    require_write(request)
    booking_datetime(data.day,data.start)
    booking_datetime(data.day,data.end)
    if data.end<=data.start: raise HTTPException(422,'Horários de bloqueio inválidos')
    with connection() as db:
        cur=db.execute('INSERT INTO blocks(day,start,end,reason) VALUES(?,?,?,?)',(data.day,data.start,data.end,data.reason))
    return {'id':cur.lastrowid}

@app.delete('/api/admin/blocks/{id}')
def remove_block(id:int,request:Request):
    require_write(request)
    with connection() as db: db.execute('DELETE FROM blocks WHERE id=?',(id,))
    return {'ok':True}

@app.get('/api/admin/integrations')
def integration_status(request:Request):
    require_admin(request)
    # Nunca expõe os tokens nem o número completo das credenciais no frontend.
    ready=bool(os.environ.get('WA_PHONE_NUMBER_ID') and os.environ.get('WA_ACCESS_TOKEN')
               and os.environ.get('WA_VERIFY_TOKEN') and os.environ.get('META_APP_SECRET'))
    enabled=os.environ.get('REMINDERS_ENABLED')=='1' and ready
    return {'whatsapp':{'type':'nao_informado' if not ready else 'cloud_api',
                        'configured':ready,'automatic_reminders_active':enabled},
            'manual_approval':True,'professional_count':1}

@app.get('/api/admin/settings')
def admin_settings(request:Request):
    require_admin(request)
    with connection() as db:
        keys=('business_name','address','whatsapp','published','lead_hours','advance_days','reminder_hours')
        result={k:setting(db,k) for k in keys}
        result['published']=result['published']=='1'
        for k in ('lead_hours','advance_days','reminder_hours'): result[k]=int(result[k])
        return result

@app.put('/api/admin/settings')
def admin_edit_settings(data:BusinessIn,request:Request):
    require_write(request)
    if data.whatsapp.strip(): valid_phone(data.whatsapp)
    with connection() as db:
        for key,value in data.model_dump().items():
            db.execute('UPDATE settings SET value=? WHERE key=?',(str(int(value)) if isinstance(value,bool) else str(value).strip(),key))
    return {'ok':True}

@app.get('/api/admin/calendar-feed')
def admin_calendar_feed_info(request:Request):
    require_admin(request)
    with connection() as db:return {'path':'/api/calendar/feed/'+setting(db,'calendar_token')+'.ics'}

@app.post('/api/admin/calendar-feed/rotate')
def admin_rotate_feed(request:Request):
    require_write(request)
    with connection() as db:
        tok=secrets.token_urlsafe(32)
        db.execute('UPDATE settings SET value=? WHERE key=?',(tok,'calendar_token'))
    return {'path':'/api/calendar/feed/'+tok+'.ics'}

@app.get('/api/calendar/feed/{token}.ics')
def private_feed(token:str):
    with connection() as db:
        if not hmac.compare_digest(token,setting(db,'calendar_token')): raise HTTPException(404,'Agenda não encontrada')
        start=now().date().isoformat()
        end=(now().date()+timedelta(days=365)).isoformat()
        books=db.execute("SELECT * FROM bookings WHERE substr(start_at,1,10) BETWEEN ? AND ? AND status IN ('aprovado','confirmado') ORDER BY start_at",(start,end)).fetchall()
        lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Precision Agenda//PT-BR//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH','X-WR-CALNAME:Agenda da Barbearia','REFRESH-INTERVAL;VALUE=DURATION:PT1H']
        for b in books: lines.extend(ics_event(b,setting(db,'business_name'),setting(db,'address'),True))
        lines.append('END:VCALENDAR')
        r=ics_response(lines)
        r.headers['Content-Disposition']='inline; filename="agenda-barbearia.ics"'
        return r

@app.get('/api/whatsapp/webhook')
def verify_whatsapp(request:Request):
    q=request.query_params
    key=os.environ.get('WA_VERIFY_TOKEN','')
    if key and q.get('hub.mode')=='subscribe' and hmac.compare_digest(q.get('hub.verify_token',''),key):
        return PlainTextResponse(q.get('hub.challenge',''))
    raise HTTPException(403,'Token de verificação incorreto')

@app.post('/api/whatsapp/webhook')
async def whatsapp_inbound(request:Request):
    secret=os.environ.get('META_APP_SECRET','')
    if not secret: raise HTTPException(503,'Webhook ainda não configurado')
    body=await request.body()
    signature=request.headers.get('X-Hub-Signature-256','')
    expected='sha256='+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected):raise HTTPException(403,'Assinatura inválida')
    payload=json.loads(body)
    for entry in payload.get('entry',[]):
      for change in entry.get('changes',[]):
       for msg in change.get('value',{}).get('messages',[]):
        interactive=msg.get('interactive',{})
        action=interactive.get('button_reply',{}).get('id','') or msg.get('button',{}).get('payload','')
        if action.startswith('CONFIRMAR:') or action.startswith('CANCELAR:'):
            kind,token=action.split(':',1)
            if len(token)>80: continue
            sender=re.sub(r'\D','',msg.get('from',''))
            with connection() as db:
                db.execute('BEGIN IMMEDIATE')
                b=db.execute('SELECT * FROM bookings WHERE public_token=?',(token,)).fetchone()
                if b and sender==b['customer_phone'] and b['status'] in ('aprovado','confirmado'):
                    new_status='confirmado' if kind=='CONFIRMAR' else 'cancelado'
                    if new_status!=b['status']:
                        db.execute('UPDATE bookings SET status=? WHERE id=?',(new_status,b['id']))
                        db.execute('INSERT INTO booking_events(booking_id,old_status,new_status,actor,occurred_at) VALUES(?,?,?,?,?)',
                            (b['id'],b['status'],new_status,'cliente_whatsapp',now().isoformat(timespec='seconds')))
                db.commit()
    return {'ok':True}

async def send_whatsapp_reminder(b):
    number_id=os.environ.get('WA_PHONE_NUMBER_ID','')
    token=os.environ.get('WA_ACCESS_TOKEN','')
    template=os.environ.get('WA_TEMPLATE_NAME','lembrete_agendamento')
    if not number_id or not token:
        raise RuntimeError('Credenciais WhatsApp Cloud API não configuradas')
    dt=datetime.fromisoformat(b['start_at'])
    payload={'messaging_product':'whatsapp','to':b['customer_phone'],'type':'template',
      'template':{'name':template,'language':{'code':'pt_BR'},'components':[
       {'type':'body','parameters':[{'type':'text','text':b['customer_name'].split()[0]},
          {'type':'text','text':b['service_name']},{'type':'text','text':dt.strftime('%d/%m/%Y')},{'type':'text','text':dt.strftime('%H:%M')}]},
       {'type':'button','sub_type':'quick_reply','index':'0','parameters':[{'type':'payload','payload':'CONFIRMAR:'+b['public_token']}]},
       {'type':'button','sub_type':'quick_reply','index':'1','parameters':[{'type':'payload','payload':'CANCELAR:'+b['public_token']}]}
      ]}}
    async with httpx.AsyncClient(timeout=18) as client:
        res=await client.post(f'https://graph.facebook.com/{GRAPH_VERSION}/{number_id}/messages',
          headers={'Authorization':f'Bearer {token}'},json=payload)
        res.raise_for_status()
        return res.json()

async def reminders_once():
    if not os.environ.get('WA_PHONE_NUMBER_ID') or not os.environ.get('WA_ACCESS_TOKEN'):
        return
    cur=now()
    with connection() as db:
        horizon=cur+timedelta(hours=int(setting(db,'reminder_hours','3')))
        db.execute('BEGIN IMMEDIATE')
        candidates=db.execute("""SELECT * FROM bookings WHERE consent_whatsapp=1 AND status IN ('aprovado','confirmado') AND reminder_state IN ('pending','failed') AND reminder_attempts<3 AND start_at>? AND start_at<=? AND substr(start_at,1,10)=? ORDER BY start_at LIMIT 15""",
           (cur.isoformat(timespec='minutes'),horizon.isoformat(timespec='minutes'),cur.date().isoformat())).fetchall()
        ids=[b['id'] for b in candidates]
        for id in ids:db.execute("UPDATE bookings SET reminder_state='sending',reminder_attempts=reminder_attempts+1,reminder_updated=? WHERE id=?",(cur.isoformat(),id))
        db.commit()
    for b in candidates:
        try:
            await send_whatsapp_reminder(b)
            with connection() as db:db.execute("UPDATE bookings SET reminder_state='sent',reminder_error='' WHERE id=?",(b['id'],))
        except Exception as e:
            # Never print access tokens or phone data to logs.
            with connection() as db:db.execute("UPDATE bookings SET reminder_state='failed',reminder_error=? WHERE id=?",(str(e)[:250],b['id']))

async def reminder_loop():
    while True:
        try:
            await reminders_once()
        except Exception as exc:
            print('Reminder worker error:',type(exc).__name__)
        await asyncio.sleep(60)

@app.get('/agendar',include_in_schema=False)
def public_page():return FileResponse(SITE/'agendar.html')

@app.get('/admin',include_in_schema=False)
def admin_page():return FileResponse(SITE/'admin.html')

app.mount('/uploads',StaticFiles(directory=UPLOADS),name='uploads')
app.mount('/',StaticFiles(directory=SITE,html=True),name='static')
