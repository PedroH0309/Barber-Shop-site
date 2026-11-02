"""Regression test for public/admin weekly scheduling; run with Python test_schedule_sync.py."""
import os
import tempfile
from datetime import timedelta

with tempfile.TemporaryDirectory() as tmp:
    os.environ['AGENDA_DATA_DIR'] = tmp
    from fastapi.testclient import TestClient
    from backend.app import app, connection, make_hash, now, init_db

    with TestClient(app) as client:
        salt = '00112233445566778899aabbccddeeff'
        with connection() as db:
            db.execute('INSERT INTO admin(id,username,salt,password_hash) VALUES(1,?,?,?)', ('tester',salt,make_hash('strongpassword123',salt)))
        r = client.post('/api/admin/login',json={'username':'tester','password':'strongpassword123'})
        assert r.status_code == 200, r.text
        headers={'X-CSRF-Token':r.json()['csrf']}
        cfg=client.get('/api/admin/settings').json()
        cfg['published']=True
        r=client.put('/api/admin/settings',json=cfg,headers=headers)
        assert r.status_code==200, r.text
        service_id=client.get('/api/public/config').json()['services'][0]['id']

        def future_weekday(day_index):
            d = now().date()+timedelta(days=10)
            for _ in range(8):
                if (d.weekday()+1)%7 == day_index:
                    return d.isoformat()
                d+=timedelta(days=1)
            raise RuntimeError('weekday missing')

        def slots(wd):
            d=future_weekday(wd)
            res=client.get('/api/public/slots',params={'service_id':service_id,'day':d})
            assert res.status_code == 200, res.text
            return res.json()['slots']

        # Default Monday-Friday, as shown to the admin, never Tuesday-Saturday.
        for wd in range(7):
            got=slots(wd)
            if 1<=wd<=5: assert '09:00' in got,(wd,got)
            else: assert got==[],(wd,got)

        # Ensure altering Monday changes Monday, not Tuesday.
        assert client.put('/api/admin/shifts/day/1',headers=headers,
            json={'weekday':1,'start':'10:00','end':'13:00'}).status_code==200
        assert '10:00' in slots(1) and '09:00' not in slots(1)
        assert '09:00' in slots(2)
        data=client.get('/api/admin/schedule').json()
        assert data['published'] is True
        assert [(x['start'],x['end']) for x in data['shifts'] if x['weekday']==1] == [('10:00','13:00')]

        # Explicit second shift; closed day has no public slots.
        assert client.post('/api/admin/shifts',headers=headers,json={'weekday':1,'start':'14:00','end':'17:00'}).status_code==200
        assert '14:00' in slots(1)
        assert client.delete('/api/admin/shifts/day/1',headers=headers).status_code==200
        assert slots(1)==[] and '09:00' in slots(2)
        assert client.put('/api/admin/shifts/day/1',headers=headers,json={'weekday':2,'start':'10:00','end':'13:00'}).status_code==422
        assert client.put('/api/admin/shifts/day/1',headers=headers,json={'weekday':1,'start':'21:00','end':'08:00'}).status_code==422
        # Previously closed days do not get regenerated during restart.
        with connection() as db: db.execute('DELETE FROM shifts')
        init_db()
        assert client.get('/api/admin/schedule').json()['shifts']==[]
        for wd in range(7): assert slots(wd)==[]
        # Publish flag also hides slots, even with a registered shift.
        assert client.post('/api/admin/shifts',headers=headers,json={'weekday':0,'start':'09:00','end':'15:00'}).status_code==200
        assert '09:00' in slots(0)
        cfg['published']=False
        assert client.put('/api/admin/settings',json=cfg,headers=headers).status_code==200
        assert slots(0)==[]
        # Deny unauthenticated mutating access.
        with TestClient(app) as anonymous:
            assert anonymous.delete('/api/admin/shifts/day/0').status_code in (401,403)

print('SCHEDULE SYNC REGRESSION TESTS PASSED')
