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
def test_identify_rejects_faceless_image(client):
    response = client.post(
        '/api/identify',
        data={'image': (io.BytesIO(_png_bytes()), 'plain.png')},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert 'No face detected' in response.get_json()['error']
