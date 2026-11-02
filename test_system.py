"""Smoke/integration tests: python test_system.py"""
import os,sys,tempfile,threading
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

DATA=tempfile.TemporaryDirectory()
os.environ['AGENDA_DATA_DIR']=DATA.name
from fastapi.testclient import TestClient
from backend.app import app,connection,make_hash,now

with TestClient(app) as client:
    def get(path, **kwargs):
        r=client.get(path,**kwargs);assert r.status_code==200,(path,r.text);return r
    assert get('/').text.find('/agendar')!=-1
    assert get('/agendar').text.find('service-grid')!=-1
    assert get('/admin').text.find('dashboard-content')!=-1
    assert get('/booking.css').text.find('service-option')!=-1
    assert get('/admin.js').text.find('loadDashboard')!=-1
    assert client.get('/api/admin/integrations').status_code==401
    cfg=get('/api/public/config').json()
    assert not cfg['published']
    assert 'customer_name' not in str(cfg)
    with connection() as db:
        db.execute('INSERT INTO admin(id,username,salt,password_hash) VALUES(1,?,?,?)',('tester','00112233445566778899aabbccddeeff',make_hash('averystrongpassword','00112233445566778899aabbccddeeff')))
    bad=client.post('/api/admin/login',json={'username':'tester','password':'wrong'})
    assert bad.status_code==401
    r=client.post('/api/admin/login',json={'username':'tester','password':'averystrongpassword'})
    assert r.status_code==200,r.text
    csrf=r.json()['csrf']; headers={'X-CSRF-Token':csrf}
    assert get('/api/admin/me').json()['csrf']==csrf
    integrations=get('/api/admin/integrations').json()
    assert not integrations['whatsapp']['configured'] and not integrations['whatsapp']['automatic_reminders_active']
    assert integrations['manual_approval'] and integrations['professional_count']==1
    config=get('/api/admin/settings').json()
    no_csrf=client.put('/api/admin/settings',json=config)
    assert no_csrf.status_code==403,(no_csrf.status_code,no_csrf.text)
    config['published']=True
    assert client.put('/api/admin/settings',headers=headers,json=config).status_code==200
    assert get('/api/public/config').json()['published']
    s=get('/api/admin/services').json()['services'][0]
    s['price_cents']=4800
    assert client.put('/api/admin/services/'+str(s['id']),headers=headers,json=s).status_code==200
    assert get('/api/public/config').json()['services'][0]['price_cents']==4800
    photo_bytes=(Path(__file__).parent/'site/assets/section-standard.jpg').read_bytes()
    upload=client.post(f'/api/admin/services/{s["id"]}/photo',headers=headers,files={'image':('foto.jpg',photo_bytes,'image/jpeg')})
    assert upload.status_code==200,upload.text
    path=upload.json()['image']
    assert path.startswith('/uploads/')
    assert get(path).headers['content-type'].startswith('image/webp')
    result=client.post('/api/admin/plans',headers=headers,json={'name':'Plano 2 cortes','description':'Pacote mensal','price_cents':8500,'period':'mensal','benefits':'2 cortes\nPrioridade','active':True})
    assert result.status_code==200,result.text
    assert len(get('/api/public/config').json()['plans'])==1
    start=now().date()+timedelta(days=2)
    while start.weekday()!=1: start+=timedelta(days=1)
    day=start.isoformat()
    times=get(f'/api/public/slots?service_id={s["id"]}&day={day}').json()['slots']
    assert '09:00' in times,times
    payload={'service_id':s['id'],'day':day,'time':'09:00','name':'Maria de Souza','phone':'11999998888','consent_whatsapp':True}
    res=client.post('/api/public/bookings',json=payload)
    assert res.status_code==201,res.text
    booked=res.json()
    assert booked['price']==48.0
    assert booked['status']=='pendente'
    assert 'google_url' not in booked
    assert get('/api/public/bookings/'+booked['token']).json()['status']=='pendente'
    assert not get('/api/public/bookings/'+booked['token']).json()['can_add_calendar']
    assert client.get('/api/public/bookings/invalid').status_code==404
    assert '09:00' not in get(f'/api/public/slots?service_id={s["id"]}&day={day}').json()['slots']
    assert '09:30' not in get(f'/api/public/slots?service_id={s["id"]}&day={day}').json()['slots']
    assert client.post('/api/public/bookings',json=payload).status_code==409
    assert client.get('/api/public/bookings/'+booked['token']+'/ics').status_code==409
    dashboard=get('/api/admin/overview?day='+day).json()
    assert dashboard['bookings'][0]['name']=='Maria de Souza'
    assert dashboard['bookings'][0]['phone']=='5511999998888'
    assert dashboard['day_count']==1
    private=get('/api/admin/calendar-feed').json()['path']
    assert 'Maria de Souza' not in get(private).text  # pending must not be in confirmed calendar
    pending=get('/api/admin/pending').json()['bookings']
    assert len(pending)==1 and pending[0]['name']=='Maria de Souza'
    assert dashboard['pending_count']==1
    assert client.get('/api/calendar/feed/invalid.ics').status_code==404
    token_new=client.post('/api/admin/calendar-feed/rotate',headers=headers).json()['path']
    assert client.get(private).status_code==404
    assert get(token_new).status_code==200
    booking_id=dashboard['bookings'][0]['id']
    assert client.patch('/api/admin/bookings/'+str(booking_id),json={'status':'aprovado'}).status_code in (401,403)
    approved=client.patch('/api/admin/bookings/'+str(booking_id),json={'status':'aprovado'},headers=headers)
    assert approved.status_code==200,approved.text
    assert get('/api/public/bookings/'+booked['token']).json()['can_add_calendar']
    assert 'calendar.google.com' in get('/api/public/bookings/'+booked['token']).json()['google_url']
    assert get('/api/public/bookings/'+booked['token']+'/ics').text.startswith('BEGIN:VCALENDAR')
    assert 'Maria de Souza' not in get('/api/public/bookings/'+booked['token']+'/ics').text
    assert 'Maria de Souza' in get(token_new).text
    assert client.patch('/api/admin/bookings/'+str(booking_id),json={'status':'recusado'},headers=headers).status_code==409
    assert client.patch('/api/admin/bookings/'+str(booking_id),json={'status':'cancelado'},headers=headers).status_code==200
    assert get('/api/public/bookings/'+booked['token']).json()['status']=='cancelado'
    assert not get('/api/public/bookings/'+booked['token']).json()['can_add_calendar']
    assert client.get('/api/public/bookings/'+booked['token']+'/ics').status_code==409
    assert '09:00' in get(f'/api/public/slots?service_id={s["id"]}&day={day}').json()['slots']
    # Another customer can request the freed slot; only barber can approve or refuse.
    retry=client.post('/api/public/bookings',json={**payload,'phone':'11988887777','name':'Renata da Silva'})
    assert retry.status_code==201,retry.text
    assert retry.json()['status']=='pendente'
    second_id=get('/api/admin/pending').json()['bookings'][0]['id']
    assert client.patch('/api/admin/bookings/'+str(second_id),json={'status':'recusado'},headers=headers).status_code==200
    assert get('/api/public/bookings/'+retry.json()['token']).json()['status']=='recusado'
    assert '09:00' in get(f'/api/public/slots?service_id={s["id"]}&day={day}').json()['slots']
    assert client.patch('/api/admin/bookings/'+str(second_id),json={'status':'aprovado'},headers=headers).status_code==409
    assert client.post('/api/admin/blocks',headers=headers,json={'day':day,'start':'09:00','end':'10:00','reason':'Pessoal'}).status_code==200
    # Two simultaneous clients cannot reserve overlapping time windows.
    concurrent_payload={**payload,'time':'14:00'}
    def reserve_once(i):
        q={**concurrent_payload,'name':f'Cliente Teste {i}'}
        return client.post('/api/public/bookings',json=q).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(reserve_once,[1,2]))
    assert sorted(statuses)==[201,409],statuses
    with connection() as db:
        events=[dict(row) for row in db.execute('SELECT * FROM booking_events ORDER BY id')]
        assert any(x['old_status']=='pendente' and x['new_status']=='aprovado' for x in events)
        assert any(x['old_status']=='pendente' and x['new_status']=='recusado' for x in events)
        assert db.execute("SELECT count(*) c FROM bookings WHERE status='pendente'").fetchone()['c']==1
    assert get('/api/public/config').json().get('customer_phone') is None
    assert client.post('/api/admin/logout',headers=headers).status_code==200
    assert client.get('/api/admin/me').status_code==401

print('ALL TESTS PASSED')
