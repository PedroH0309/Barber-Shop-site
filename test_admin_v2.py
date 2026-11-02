"""Additional auth, audit and admin v2 integration tests (isolated temporary database)."""
import os
import tempfile
from datetime import timedelta

with tempfile.TemporaryDirectory() as tmp:
    os.environ['AGENDA_DATA_DIR'] = tmp
    from fastapi.testclient import TestClient
    from backend.app import app, connection, make_hash, now

    with TestClient(app) as client:
        assert client.put('/api/admin/credentials', json={'username':'barbeiro','current_password':'X','new_password':'LongEnough123456'}).status_code == 401
        assert client.get('/api/admin/bookings/1/history').status_code == 401
        salt = '00112233445566778899aabbccddeeff'
        with connection() as db:
            db.execute('INSERT INTO admin(id,username,salt,password_hash) VALUES(1,?,?,?)',
                       ('barbeiro', salt, make_hash('OldPassword123456', salt)))
        old_login = client.post('/api/admin/login', json={'username':'barbeiro','password':'OldPassword123456'})
        assert old_login.status_code == 200
        csrf = {'X-CSRF-Token': old_login.json()['csrf']}
        assert client.get('/api/admin/me').json()['username'] == 'barbeiro'
        new_creds={'username':'novo.barbeiro','current_password':'OldPassword123456','new_password':'NewPassword123456'}
        assert client.put('/api/admin/credentials', json=new_creds).status_code == 403  # CSRF
        assert client.put('/api/admin/credentials', headers=csrf, json={**new_creds,'username':'bad space'}).status_code == 422
        assert client.put('/api/admin/credentials', headers=csrf, json={**new_creds,'new_password':'short'}).status_code == 422
        assert client.put('/api/admin/credentials', headers=csrf, json={**new_creds,'current_password':'wrong'}).status_code == 403
        assert client.get('/api/admin/me').status_code == 200
        res=client.put('/api/admin/credentials',headers=csrf,json=new_creds)
        assert res.status_code == 200,res.text
        assert client.get('/api/admin/me').status_code == 401
        assert client.post('/api/admin/login',json={'username':'barbeiro','password':'OldPassword123456'}).status_code == 401
        res=client.post('/api/admin/login',json={'username':'novo.barbeiro','password':'NewPassword123456'})
        assert res.status_code == 200,res.text
        csrf = {'X-CSRF-Token': res.json()['csrf']}
        assert client.get('/api/admin/me').json()['username']=='novo.barbeiro'
        assert client.get('/api/admin/bookings/1/history').status_code == 404
        config=client.get('/api/admin/settings').json()
        config['published']=True
        assert client.put('/api/admin/settings', headers=csrf,json=config).status_code==200
        service=client.get('/api/admin/services').json()['services'][0]
        day=now().date()+timedelta(days=2)
        while day.weekday()!=1: day+=timedelta(days=1)
        booking=client.post('/api/public/bookings',json={'service_id':service['id'],'day':day.isoformat(),'time':'09:00','name':'Cecilia Costa','phone':'11987654321'}).json()
        assert booking['status']=='pendente'
        bid=client.get('/api/admin/pending').json()['bookings'][0]['id']
        history=client.get(f'/api/admin/bookings/{bid}/history').json()
        assert history['booking']['name']=='Cecilia Costa'
        assert not history['events']
        assert client.patch(f'/api/admin/bookings/{bid}',headers=csrf,json={'status':'aprovado'}).status_code == 200
        history=client.get(f'/api/admin/bookings/{bid}/history').json()
        assert len(history['events'])==1 and history['events'][0]['new_status']=='aprovado'
        assert client.get('/api/public/bookings/'+booking['token']).json().get('name') is None
        assert client.post('/api/admin/logout',headers=csrf).status_code==200
        assert client.get(f'/api/admin/bookings/{bid}/history').status_code==401
print('ADMIN V2 TESTS PASSED')
