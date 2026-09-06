# Keccak-256 compatibility layer for Solidity-style record hashing.
#
# Solidity's keccak256() and web3.py's Web3.keccak() both use the Keccak-256
# sponge (FIPS 202, rate=1088, capacity=576, pad10*1, 256-bit output). This
# module computes exactly that, independent of whether web3 is installed.
#
# Preferred backend: ``eth_hash`` (pure Python, no compiler needed). Fallback:
# ``web3`` (if installed). This keeps the on-chain record hash computable even
# when web3 is absent, so the project remains fully runnable offline.
from __future__ import annotations

from typing import Optional

_BACKEND: Optional[object] = None
_BACKEND_NAME: str = "none"


def _backend():
    global _BACKEND, _BACKEND_NAME
    if _BACKEND is not None:
        return _BACKEND, _BACKEND_NAME
    # Prefer eth_hash (pure Python Keccak).
    try:
        import eth_hash.auto as _eth_hash  # type: ignore[import]

        def _k(data: bytes) -> bytes:
            return _eth_hash.keccak(data)

        _BACKEND = _k
        _BACKEND_NAME = "eth_hash"
        return _BACKEND, _BACKEND_NAME
    except Exception:
        pass

    # Fall back to web3.
    try:
        from web3 import Web3  # type: ignore[import]

        def _k(data: bytes) -> bytes:
            return Web3.keccak(data)

        _BACKEND = _k
        _BACKEND_NAME = "web3"
        return _BACKEND, _BACKEND_NAME
    except Exception:
        pass

    raise RuntimeError(
        "No Keccak-256 backend available. Install either `eth-hash` or `web3` "
        "to compute on-chain record hashes. Example: pip install eth-hash"
    )


def keccak256(data: bytes) -> bytes:
    """Return the Keccak-256 digest of *data* as 32 bytes (matches Solidity keccak256)."""
    backend, _ = _backend()
    return backend(data)


def keccak256_hex(data: bytes) -> str:
    return "0x" + keccak256(data).hex()


def keccak256_of_json_payload(
    subject_id: str,
    similarity: float,
    result: str,
    probe_image_hash: str,
    web_result_count: int,
    schema: str = "v1",
) -> bytes:
    from json import dumps

    payload = {
        "subject_id": subject_id,
        "similarity": similarity,
        "result": result,
        "probe_image_hash": probe_image_hash,
        "web_result_count": web_result_count,
        "record_schema": schema,
        "chain": "polygon-amoy",
    }
    raw = dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return keccak256(raw)
