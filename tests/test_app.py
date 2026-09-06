# Integration tests through the Flask test client using an isolated data dir.
import io
import os
import tempfile

import numpy as np
import pytest

os.environ.setdefault('FCV_DATA_DIR', tempfile.mkdtemp(prefix='fcv-test-'))

from app import app  # noqa: E402  (import after the data-dir override)


def _png_bytes():
    import cv2
    image = np.full((240, 320, 3), 32, dtype=np.uint8)
    ok, buffer = cv2.imencode('.png', image)
    assert ok is True
    return buffer.tobytes()


def _models_present():
    from config import SFACE_MODEL_PATH, YUNET_MODEL_PATH
    return YUNET_MODEL_PATH.exists() and SFACE_MODEL_PATH.exists()


@pytest.fixture()
def client():
    app.config['TESTING'] = True
    with app.test_client() as test_client:
        yield test_client


def test_dashboard_ok(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Dashboard' in response.data


def test_ledger_page_ok(client):
    response = client.get('/ledger')
    assert response.status_code == 200


def test_verify_page_ok(client):
    response = client.get('/verify')
    assert response.status_code == 200


def test_health_endpoint_ok(client):
    response = client.get('/health')
    assert response.status_code in (200, 503)
    payload = response.get_json()
    assert payload['status'] in ('ok', 'degraded')
    assert 'models_available' in payload
    assert 'blocks' in payload


def test_demo_page_ok(client):
    response = client.get('/demo')
    assert response.status_code == 200
    assert b'Live pipeline demo' in response.data
    assert b'stepper' in response.data


def test_demo_run_without_samples_returns_409(client):
    # The test data dir has no probes, so the demo must degrade gracefully.
    response = client.post('/demo/run')
    assert response.status_code == 409
    assert response.get_json()['ok'] is False
    assert 'No sample probe' in response.get_json()['error']


def test_api_chain_starts_valid(client):
    response = client.get('/api/chain/validate')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ok'] is True
    assert payload['valid'] is True


def test_register_requires_image(client):
    response = client.post('/api/register', data={'name': 'Nobody'})
    assert response.status_code == 400
    assert 'No image' in response.get_json()['error']


@pytest.mark.skipif(not _models_present(), reason='ONNX models not downloaded')
def test_register_rejects_faceless_image(client):
    response = client.post(
        '/api/register',
        data={'name': 'Nobody', 'image': (io.BytesIO(_png_bytes()), 'plain.png')},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'No face detected' in response.get_json()['error']


@pytest.mark.skipif(not _models_present(), reason='ONNX models not downloaded')
def test_api_docs_page_ok(client):
    response = client.get('/api/docs')
    assert response.status_code == 200
    assert b'API reference' in response.data
    assert b'/api/identify' in response.data
    assert b'/api/chain/validate' in response.data


def test_history_export_unknown_subject_returns_404(client):
    response = client.get('/api/history/does-not-exist/export')
    assert response.status_code == 404
    assert response.get_json()['ok'] is False


def test_history_export_returns_downloadable_json(client):
    # Enroll a subject directly through the store, then export its records.
    import numpy as np
    from app import service as svc  # module-level attribute lookup, not Flask attr
    if svc.store.count() == 0:
        embedding = np.ones(128, dtype=np.float32)
        svc.store.add_subject('Export Test', embedding)
    subject = svc.store.list_subjects()[0]
    response = client.get(f"/api/history/{subject['subject_id']}/export")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ok'] is True
    assert payload['subject']['subject_id'] == subject['subject_id']
    assert 'verification_records' in payload
    assert 'events' in payload
    assert 'exported_at' in payload
    assert 'attachment' in response.headers.get('Content-Disposition', '')


def test_identify_rejects_faceless_image(client):
    response = client.post(
        '/api/identify',
        data={'image': (io.BytesIO(_png_bytes()), 'plain.png')},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'No face detected' in response.get_json()['error']
