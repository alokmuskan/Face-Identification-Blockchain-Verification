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


_CANONICAL_PAYLOAD_FIELDS = (
    "subject_id",
    "similarity",
    "result",
    "probe_image_hash",
    "web_result_count",
    "record_schema",
    "chain",
    "local_block_hash",  # present only when set (backward compatible with legacy records)
)


def canonical_payload(
    subject_id: str,
    similarity: float,
    result: str,
    probe_image_hash: str,
    web_result_count: int,
    schema: str = "v1",
    *,
    local_block_hash: str = "",
    chain: str = "polygon-amoy",
) -> dict:
    """Build the canonical record payload dict.

    This is the single source of truth for the payload shape that is hashed
    on-chain by ``createRecord(...)`` as ``recordHash``. Any change to the
    record shape should happen here only.

    ``local_block_hash`` is optional. When present, it ties the on-chain record
    to the local ledger block that carried the matching ``contract_tx_hash``.
    """
    payload = {
        "subject_id": subject_id,
        "similarity": similarity,
        "result": result,
        "probe_image_hash": probe_image_hash,
        "web_result_count": web_result_count,
        "record_schema": schema,
        "chain": chain,
    }
    # Backward compatibility: the traceability field is only committed when it
    # actually carries a value. Records submitted before Phase 3 (local_block_hash
    # unset) were hashed without this field, so omitting it when empty keeps the
    # existing on-chain proof reproducible. New enriched records pass a real
    # local_block_hash, which then participates in the hash as before.
    if local_block_hash:
        payload["local_block_hash"] = local_block_hash
    return payload


def canonical_payload_json_bytes(
    subject_id: str,
    similarity: float,
    result: str,
    probe_image_hash: str,
    web_result_count: int,
    schema: str = "v1",
    *,
    local_block_hash: str = "",
    chain: str = "polygon-amoy",
) -> bytes:
    """Serialize the canonical payload to the exact JSON bytes that are hashed.

    Uses ``sort_keys=True`` and the compact ``separators`` so the serialized
    bytes are deterministic and match what web3 / Solidity would compute.
    """
    from json import dumps

    return dumps(
        canonical_payload(
            subject_id=subject_id,
            similarity=similarity,
            result=result,
            probe_image_hash=probe_image_hash,
            web_result_count=web_result_count,
            schema=schema,
            local_block_hash=local_block_hash,
            chain=chain,
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def keccak256_of_json_payload(
    subject_id: str,
    similarity: float,
    result: str,
    probe_image_hash: str,
    web_result_count: int,
    schema: str = "v1",
    *,
    local_block_hash: str = "",
    chain: str = "polygon-amoy",
) -> bytes:
    """Return ``keccak256(canonical_payload_json_bytes(...))``.

    This is the same value stored on-chain by ``createRecord(...)`` as
    ``recordHash``.
    """
    return keccak256(canonical_payload_json_bytes(
        subject_id=subject_id,
        similarity=similarity,
        result=result,
        probe_image_hash=probe_image_hash,
        web_result_count=web_result_count,
        schema=schema,
        local_block_hash=local_block_hash,
        chain=chain,
    ))
