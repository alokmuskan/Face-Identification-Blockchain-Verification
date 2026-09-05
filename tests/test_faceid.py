# Unit tests for the similarity helper and the subject registry.
import numpy as np
import pytest

from faceid.similarity import cosine_similarity
from faceid.store import FaceStore


def test_cosine_similarity_basics():
    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    assert cosine_similarity(a, a) == pytest.approx(1.0)
    assert cosine_similarity(a, -a) == pytest.approx(-1.0)
    assert cosine_similarity(a, np.array([0.0, 1.0, 0.0], dtype=np.float32)) == pytest.approx(0.0)
    assert cosine_similarity(a, np.zeros(3, dtype=np.float32)) == 0.0


def test_store_round_trip_and_match(tmp_path):
    path = tmp_path / 'face_store.json'
    store = FaceStore(store_path=path, threshold=0.363)
    base = np.random.default_rng(7).normal(size=128).astype(np.float32)
    record = store.add_subject('Alice Example', base)
    assert record['embedding_count'] == 1
    assert record['embedding_hash']

    probe = base + np.random.default_rng(1).normal(scale=0.01, size=128).astype(np.float32)
    match = store.match(probe.astype(np.float32))
    assert match['matched'] is True
    assert match['subject']['name'] == 'Alice Example'

    far = np.random.default_rng(42).normal(size=128).astype(np.float32)
    miss = store.match(far)
    assert miss['matched'] is False
    assert miss['subject'] is None


def test_duplicate_registration_reuses_identity(tmp_path):
    store = FaceStore(store_path=tmp_path / 'fs.json', threshold=0.363)
    first = store.add_subject('Bob', np.ones(128, dtype=np.float32))
    second = store.add_subject('Bob', np.full(128, 0.5, dtype=np.float32))
    assert first['subject_id'] == second['subject_id']
    assert second['embedding_count'] == 2


def test_embedding_cap(tmp_path):
    store = FaceStore(store_path=tmp_path / 'fs.json', threshold=0.363)
    rng = np.random.default_rng(3)
    for _ in range(6):
        store.add_subject('Cap Test', rng.normal(size=128).astype(np.float32))
    subjects = store.list_subjects()
    assert len(subjects) == 1
    assert subjects[0]['embedding_count'] == 3


def test_persistence_round_trip(tmp_path):
    path = tmp_path / 'fs.json'
    store = FaceStore(store_path=path, threshold=0.363)
    base = np.random.default_rng(11).normal(size=128).astype(np.float32)
    created = store.add_subject('Carol', base, image_path='data/faces/abc.png')
    reloaded = FaceStore(store_path=path, threshold=0.363)
    assert reloaded.count() == 1
    fetched = reloaded.get(created['subject_id'])
    assert fetched is not None
    assert fetched['images'] == ['data/faces/abc.png']
    assert reloaded.match(base)['matched'] is True


def _models_present():
    from config import SFACE_MODEL_PATH, YUNET_MODEL_PATH
    return YUNET_MODEL_PATH.exists() and SFACE_MODEL_PATH.exists()


@pytest.mark.skipif(not _models_present(), reason='ONNX models not downloaded')
def test_engine_rejects_image_without_face():
    from faceid.engine import FaceEngine, FaceEngineError
    engine = FaceEngine()
    image = np.full((240, 320, 3), 32, dtype=np.uint8)
    with pytest.raises(FaceEngineError):
        engine.embedding(image)
