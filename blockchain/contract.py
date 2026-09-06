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
from typing import Any, Optional

from ._keccak import canonical_payload_json_bytes, keccak256, keccak256_hex, keccak256_of_json_payload

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


def compute_record_hash(
    subject_id: str,
    similarity: float,
    result: str,
    probe_image_hash: str,
    web_result_count: int,
    schema: str = "v1",
) -> str:
    """Return the keccak256 record hash (utf8 hex, with ``0x`` prefix) for the
    canonical payload.

    This matches the representation returned by ``get_record_hash(...)`` and
    the value stored on-chain by ``createRecord(...)`` as ``recordHash``, so
    the local and on-chain hashes compare equal directly.
    """
    return "0x" + keccak256_of_json_payload(
        subject_id=subject_id,
        similarity=similarity,
        result=result,
        probe_image_hash=probe_image_hash,
        web_result_count=web_result_count,
        schema=schema,
    ).hex()


class ContractBridge:
    """Thin wrapper around FaceVerificationHub on Polygon Amoy.

    The web3 dependency is imported lazily, so this module can be imported
    even when web3 is not installed. Instantiation only stores the config;
    the actual RPC connection and contract binding happen on first use.
    """

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        private_key: str,
        chain_id: int = 80143,
    ) -> None:
        self._rpc_url = rpc_url
        self._contract_address = contract_address
        self._private_key = private_key
        self._chain_id = chain_id
        self._w3: Any = None
        self._account: Any = None
        self._contract: Any = None

    def _ensure_web3(self) -> None:
        """Lazy-import web3 and bind the contract on first RPC use."""
        if self._w3 is not None:
            return
        try:
            from web3 import Web3  # type: ignore[import]
            from web3.eth import Account  # type: ignore[import]
        except Exception as exc:
            raise RuntimeError(
                "web3 is required for on-chain operations. Install it with: "
                "pip install web3"
            ) from exc

        self._w3 = Web3(Web3.HTTPProvider(self._rpc_url))
        if not self._w3.is_connected():
            raise RuntimeError(f"Cannot connect to RPC at {self._rpc_url}")
        if self._w3.eth.chain_id != self._chain_id:
            logger.warning(
                "Connected chain id %s differs from expected Polygon Amoy %s",
                self._w3.eth.chain_id,
                self._chain_id,
            )
        self._account = Account.from_key(self._private_key)
        self._contract_address = Web3.to_checksum_address(self._contract_address)
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
        self._ensure_web3()
        payload_bytes = canonical_payload_json_bytes(
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
        self._ensure_web3()
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
        self._ensure_web3()
        expected_bytes32 = (
            self._w3.to_bytes(hexstr=expected_hash_utf8)
            if expected_hash_utf8
            else b"\x00" * 32
        )
        try:
            return bool(self._contract.functions.verifyRecord(subject_id, expected_bytes32).call())
        except Exception:
            return False

    def record_count(self) -> int:
        self._ensure_web3()
        return int(self._contract.functions.recordCount().call())

    def last_record_at(self) -> int:
        self._ensure_web3()
        return int(self._contract.functions.lastRecordAt().call())

    def last_record_by(self) -> str:
        self._ensure_web3()
        return self._contract.functions.lastRecordBy().call()
