# Optional on-chain bridge for FaceVerificationHub on Polygon Amoy.
#
# This module is only active when a deployment config is provided. When the
# contract address and a funded wallet are configured, the local pipeline can
# write a matching record to the smart contract and store the tx hash in the
# local ledger for cross-verification.
#
# Keep real private keys and funded wallet addresses out of version control.
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from web3 import Web3
from web3.eth import Account

from ._keccak import keccak256, keccak256_hex, keccak256_of_json_payload

logger = logging.getLogger(__name__)

# ABI is shipped in the repo next to the Solidity source.
_ABI_PATH = Path(__file__).resolve().parent.parent / "contracts" / "FaceVerificationHub.abi.json"


def _load_abi() -> list:
    if not _ABI_PATH.exists():
        raise RuntimeError(
            "On-chain ABI not found at contracts/FaceVerificationHub.abi.json. "
            "The Solidity build step should produce this file."
        )
    return json.loads(_ABI_PATH.read_text(encoding="utf-8"))


def _scaled_similarity(similarity: float) -> int:
    # Store similarity as an integer: similarity * 1e6.
    return int(round(max(0.0, min(1.0, similarity)) * 1_000_000))


def _record_payload(
    subject_id: str,
    similarity: float,
    result: str,
    probe_image_hash: str,
    web_result_count: int,
    schema: str = "v1",
) -> bytes:
    """Build the exact canonical JSON payload bytes that are hashed on-chain.

    The on-chain ``recordHash`` is ``keccak256(_record_payload(...))``. This
    helper is the single source of truth for that payload so the Python side
    computes exactly the same bytes as the contract.
    """
    payload = {
        "subject_id": subject_id,
        "similarity": similarity,
        "result": result,
        "probe_image_hash": probe_image_hash,
        "web_result_count": web_result_count,
        "record_schema": schema,
        "chain": "polygon-amoy",
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def compute_record_hash(
    subject_id: str,
    similarity: float,
    result: str,
    probe_image_hash: str,
    web_result_count: int,
    schema: str = "v1",
) -> str:
    """Return the keccak256 record hash (utf8 hex) for the canonical payload.

    This is the same value stored on-chain by ``createRecord(...)`` as
    ``recordHash``.
    """
    return keccak256_of_json_payload(
        subject_id=subject_id,
        similarity=similarity,
        result=result,
        probe_image_hash=probe_image_hash,
        web_result_count=web_result_count,
        schema=schema,
    ).hex()


class ContractBridge:
    """Thin wrapper around FaceVerificationHub on Polygon Amoy."""

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        private_key: str,
        chain_id: int = 80143,
    ) -> None:
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self._w3.is_connected():
            raise RuntimeError(f"Cannot connect to RPC at {rpc_url}")
        if self._w3.eth.chain_id != chain_id:
            logger.warning(
                "Connected chain id %s differs from expected Polygon Amoy %s",
                self._w3.eth.chain_id,
                chain_id,
            )
        self._contract_address = Web3.to_checksum_address(contract_address)
        self._account: Account = Account.from_key(private_key)
        self._contract = self._w3.eth.contract(
            address=self._contract_address, abi=_load_abi()
        )

    # -- record submission -----------------------------------------------------

    def submit_record(
        self,
        subject_id: str,
        similarity: float,
        result: str,
        probe_image_hash: str,
        web_result_count: int,
    ) -> str:
        """Write a record on-chain and return the tx hash (utf8 hex)."""
        payload_bytes = _record_payload(
            subject_id=subject_id,
            similarity=similarity,
            result=result,
            probe_image_hash=probe_image_hash,
            web_result_count=web_result_count,
        )
        record_hash = keccak256(payload_bytes)
        scaled = _scaled_similarity(similarity)

        func = self._contract.functions.createRecord(
            subject_id=subject_id,
            recordHash=record_hash,
            similarity=scaled,
            result=result,
            probeImageHash=probe_image_hash,
            webResultCount=web_result_count,
        )
        tx = func.build_transaction(
            {
                "chainId": self._w3.eth.chain_id,
                "gas": 300_000,
                "gasPrice": self._w3.eth.gas_price,
                "nonce": self._w3.eth.get_transaction_count(self._account.address),
                "from": self._account.address,
            }
        )
        signed = self._account.sign_transaction(tx)
        tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info(
            "On-chain record submitted: subject=%s tx=%s",
            subject_id,
            tx_hash.hex(),
        )
        return tx_hash.hex()

    # -- queries --------------------------------------------------------------

    def get_record_hash(self, subject_id: str) -> Optional[str]:
        """Return the on-chain record hash (utf8 hex) for *subject_id*, or None."""
        try:
            raw = self._contract.functions.getRecord(subject_id).call()
        except Exception:
            return None
        if raw == b"\x00" * 32:
            return None
        return "0x" + raw.hex()

    def verify_record(self, subject_id: str, expected_hash_utf8: str) -> bool:
        """Return True when the on-chain ``recordHash`` matches *expected_hash_utf8*.

        *expected_hash_utf8* should already be the keccak256 hex of the canonical
        payload (as returned by ``compute_record_hash(...)``). It is **not** re-hashed
        here, because the on-chain value is also the keccak256 of the payload.
        """
        expected_bytes32 = Web3.to_bytes(hexstr=expected_hash_utf8) if expected_hash_utf8 else b"\x00" * 32
        try:
            return bool(self._contract.functions.verifyRecord(subject_id, expected_bytes32).call())
        except Exception:
            return False

    def record_count(self) -> int:
        return int(self._contract.functions.recordCount().call())

    def last_record_at(self) -> int:
        return int(self._contract.functions.lastRecordAt().call())

    def last_record_by(self) -> str:
        return self._contract.functions.lastRecordBy().call()
