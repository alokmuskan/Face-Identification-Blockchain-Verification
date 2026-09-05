# Persistent registry of enrolled subjects and their SFace embeddings.
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from config import FACE_STORE_PATH, MATCH_THRESHOLD, MAX_EMBEDDINGS_PER_SUBJECT, MAX_IMAGES_PER_SUBJECT
from faceid.similarity import cosine_similarity


class FaceStore:
    # Stores one record per subject; several embeddings per subject improve
    # matching robustness. Persisted as JSON with atomic replacement.

    def __init__(self, store_path: Path = FACE_STORE_PATH, threshold: float = MATCH_THRESHOLD) -> None:
        self.store_path = Path(store_path)
        self.threshold = float(threshold)
        self.max_embeddings = MAX_EMBEDDINGS_PER_SUBJECT
        self.max_images = MAX_IMAGES_PER_SUBJECT
        self._lock = threading.RLock()
        self._subjects: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        raw = json.loads(self.store_path.read_text(encoding='utf-8'))
        for subject_id, record in raw.get('subjects', {}).items():
            record['subject_id'] = subject_id
            record['embeddings'] = [np.asarray(item, dtype=np.float32) for item in record.get('embeddings', [])]
            self._subjects[subject_id] = record

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload: Dict[str, Any] = {'subjects': {}}
        for subject_id, record in self._subjects.items():
            payload['subjects'][subject_id] = {
                'subject_id': subject_id,
                'name': record['name'],
                'created_at': record['created_at'],
                'updated_at': record['updated_at'],
                'images': record.get('images', []),
                'embeddings': [item.tolist() for item in record.get('embeddings', [])],
            }
        tmp_path = self.store_path.with_suffix('.tmp')
        tmp_path.write_text(json.dumps(payload), encoding='utf-8')
        os.replace(tmp_path, self.store_path)

    @staticmethod
    def _slugify(name: str) -> str:
        normalized = ''.join(ch if ch.isalnum() else '-' for ch in name.strip().lower())
        parts = [part for part in normalized.split('-') if part]
        return '-'.join(parts) if parts else 'subject'

    def _find_id_by_name(self, name: str) -> Optional[str]:
        wanted = self._slugify(name)
        for subject_id, record in self._subjects.items():
            if self._slugify(record['name']) == wanted:
                return subject_id
        return None

    @staticmethod
    def _embedding_hash(embeddings: List[np.ndarray]) -> str:
        joined = b''.join(np.asarray(item, dtype=np.float32).tobytes() for item in embeddings)
        return hashlib.sha256(joined).hexdigest()

    @staticmethod
    def _public(record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'subject_id': record['subject_id'],
            'name': record['name'],
            'created_at': record['created_at'],
            'updated_at': record['updated_at'],
            'images': list(record.get('images', [])),
            'embedding_count': len(record.get('embeddings', [])),
            'embedding_hash': FaceStore._embedding_hash(record.get('embeddings', [])),
        }

    def add_subject(self, name: str, embedding: np.ndarray, image_path: Optional[str] = None) -> Dict[str, Any]:
        # Creates the subject on first sight and reuses the identity on later
        # registrations of the same name, appending capped embeddings.
        with self._lock:
            now = time.time()
            subject_id = self._find_id_by_name(name)
            if subject_id is None:
                subject_id = f'{self._slugify(name)}-{uuid.uuid4().hex[:6]}'
                self._subjects[subject_id] = {
                    'subject_id': subject_id,
                    'name': name.strip(),
                    'created_at': now,
                    'updated_at': now,
                    'images': [],
                    'embeddings': [],
                }
            record = self._subjects[subject_id]
            record['updated_at'] = now
            record['embeddings'].append(np.asarray(embedding, dtype=np.float32).flatten())
            if len(record['embeddings']) > self.max_embeddings:
                del record['embeddings'][: len(record['embeddings']) - self.max_embeddings]
            if image_path:
                record['images'].append(image_path)
                if len(record['images']) > self.max_images:
                    del record['images'][: len(record['images']) - self.max_images]
            self._save()
            return self._public(record)

    def match(self, embedding: np.ndarray) -> Dict[str, Any]:
        # Best cosine similarity across every stored embedding of every subject.
        with self._lock:
            best_score = -1.0
            best_record: Optional[Dict[str, Any]] = None
            for record in self._subjects.values():
                for stored in record.get('embeddings', []):
                    score = cosine_similarity(embedding, stored)
                    if score > best_score:
                        best_score = score
                        best_record = record
            matched = best_record is not None and best_score >= self.threshold
            return {
                'matched': bool(matched),
                'similarity': round(best_score, 4) if best_record is not None else 0.0,
                'threshold': self.threshold,
                'subject': self._public(best_record) if matched and best_record is not None else None,
                'candidate': self._public(best_record) if not matched and best_record is not None else None,
            }

    def get(self, subject_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._subjects.get(subject_id)
            return self._public(record) if record is not None else None

    def list_subjects(self) -> List[Dict[str, Any]]:
        with self._lock:
            records = sorted(self._subjects.values(), key=lambda item: item['created_at'])
            return [self._public(record) for record in records]

    def count(self) -> int:
        with self._lock:
            return len(self._subjects)
