"""Precision Admin PWA checks: public shell is installable, API stays protected."""
import json
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as temp:
    os.environ['AGENDA_DATA_DIR'] = temp
    from backend.app import app
    with TestClient(app) as client:
        manifest = client.get('/admin-manifest.webmanifest')
        assert manifest.status_code == 200
        parsed = json.loads(manifest.text)
        assert parsed['start_url'] == '/admin'
        assert parsed['display'] == 'standalone'
        assert parsed['icons'] and all(client.get(icon['src']).status_code == 200 for icon in parsed['icons'])
        assert client.get('/admin-pwa.js').status_code == 200
        assert client.get('/admin-mobile.css').status_code == 200
        sw = client.get('/admin-sw.js')
        assert sw.status_code == 200
        assert sw.headers['cache-control'] == 'no-store'
        assert 'caches.open(' not in sw.text
        assert client.get('/admin').headers['cache-control'] == 'no-store'
        assert client.get('/api/admin/me').status_code == 401
        assert client.get('/api/admin/clients').status_code == 401
        assert client.get('/api/admin/pending').status_code == 401
        assert client.get('/').status_code == 200
        assert client.get('/agendar').status_code == 200
print('ADMIN PWA API TESTS PASSED')

