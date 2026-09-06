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
import threading
from pathlib import Path
from typing import Any, Optional

from ._keccak import (
    canonical_payload_json_bytes,
    keccak256,
    keccak256_of_json_payload,
)

logger = logging.getLogger(__name__)

# ABI is shipped in the repo next to the Solidity source.
_ABI_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "FaceVerificationHub.abi.json"
)


def _load_abi() -> list:
    """Load the deployed contract ABI."""
    if not _ABI_PATH.exists():
        raise RuntimeError(
            "On-chain ABI not found at "
            "contracts/FaceVerificationHub.abi.json. "
            "The Solidity build step should produce this file."
        )

    return json.loads(_ABI_PATH.read_text(encoding="utf-8"))


def _scaled_similarity(similarity: float) -> int:
    """
    Store similarity as an integer scaled by 1,000,000.

    Example:
        0.9999 -> 999900
    """
    return int(
        round(
            max(0.0, min(1.0, similarity))
            * 1_000_000
        )
    )


def compute_record_hash(
    subject_id: str,
    similarity: float,
    result: str,
    probe_image_hash: str,
    web_result_count: int,
    schema: str = "v1",
    *,
    local_block_hash: str = "",
) -> str:
    """
    Return the Keccak-256 record hash.

    The returned value:
        - is hexadecimal
        - includes the 0x prefix
        - matches the hash stored on-chain by createRecord()
    When ``local_block_hash`` is provided, the record hash also commits to the
    local ledger block that carried the matching ``contract_tx_hash``.
    """

    return "0x" + keccak256_of_json_payload(
        subject_id=subject_id,
        similarity=similarity,
        result=result,
        probe_image_hash=probe_image_hash,
        web_result_count=web_result_count,
        schema=schema,
        local_block_hash=local_block_hash,
    ).hex()


class ContractBridge:
    """
    Thin wrapper around FaceVerificationHub on Polygon Amoy.

    Web3 is imported lazily so this module can still be imported when
    web3.py is not installed.

    The RPC connection and contract binding happen on first blockchain use.
    """

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        private_key: str,
        chain_id: int = 80002,
    ) -> None:

        self._rpc_url = rpc_url
        self._contract_address = contract_address
        self._private_key = private_key
        self._chain_id = chain_id

        self._w3: Any = None
        self._account: Any = None
        self._contract: Any = None

        # Prevent multiple Flask requests from allocating the same nonce.
        self._tx_lock = threading.Lock()

    def _ensure_web3(self) -> None:
        """Lazy-import web3 and bind the contract on first RPC use."""

        if self._w3 is not None:
            return

        try:
            from web3 import Web3
            from eth_account import Account
        except Exception as exc:
            raise RuntimeError(
                "web3 is required for on-chain operations. "
                "Install it with: pip install web3"
            ) from exc

        # Connect to Polygon Amoy.
        self._w3 = Web3(
            Web3.HTTPProvider(self._rpc_url)
        )

        if not self._w3.is_connected():
            raise RuntimeError(
                f"Cannot connect to RPC at {self._rpc_url}"
            )

        # Confirm expected chain.
        actual_chain_id = self._w3.eth.chain_id

        if actual_chain_id != self._chain_id:
            logger.warning(
                "Connected chain id %s differs from expected Polygon Amoy %s",
                actual_chain_id,
                self._chain_id,
            )

        # Load deployment wallet.
        self._account = Account.from_key(
            self._private_key
        )

        # Normalize contract address.
        self._contract_address = Web3.to_checksum_address(
            self._contract_address
        )

        # Bind deployed contract.
        self._contract = self._w3.eth.contract(
            address=self._contract_address,
            abi=_load_abi(),
        )

    # -------------------------------------------------------------------------
    # RECORD SUBMISSION
    # -------------------------------------------------------------------------

    def submit_record(
        self,
        subject_id: str,
        similarity: float,
        result: str,
        probe_image_hash: str,
        web_result_count: int,
        *,
        local_block_hash: str = "",
    ) -> str:
        """
        Write a verification record on-chain.

        Returns:
            Transaction hash as a hexadecimal string.

        The transaction is considered successful only after Polygon
        confirms it in a block with receipt status == 1.
        When ``local_block_hash`` is provided, the same canonical payload is
        used and the printed record summary includes the local block hash so the
        on-chain record can be tied back to the local ledger.
        """

        self._ensure_web3()

        # ---------------------------------------------------------------------
        # 1. Build canonical payload
        # ---------------------------------------------------------------------

        payload_bytes = canonical_payload_json_bytes(
            subject_id=subject_id,
            similarity=similarity,
            result=result,
            probe_image_hash=probe_image_hash,
            web_result_count=web_result_count,
            local_block_hash=local_block_hash,
        )

        # ---------------------------------------------------------------------
        # 2. Generate record hash
        # ---------------------------------------------------------------------

        record_hash = keccak256(payload_bytes)

        # Similarity is stored on-chain as an integer.
        scaled = _scaled_similarity(similarity)

        # ---------------------------------------------------------------------
        # 3. Print record information
        # ---------------------------------------------------------------------
        print()
        print("========== POLYGON AMOY RECORD ==========")
        print(f"Subject ID       : {subject_id}")
        print(f"Record Hash      : 0x{record_hash.hex()}")
        print(f"Similarity       : {similarity}")
        print(f"Similarity Stored: {scaled}")
        print(f"Result           : {result}")
        print(f"Web Results      : {web_result_count}")
        if local_block_hash:
            print(f"Local Block Hash : {local_block_hash}")
        print("==========================================")
        print()

        # ---------------------------------------------------------------------
        # 4. Prepare Solidity function call
        # ---------------------------------------------------------------------

        if local_block_hash:
            func = self._contract.functions.createRecord(
                subject_id,
                record_hash,
                scaled,
                result,
                probe_image_hash,
                web_result_count,
                local_block_hash,
            )
        else:
            func = self._contract.functions.createRecord(
                subject_id,
                record_hash,
                scaled,
                result,
                probe_image_hash,
                web_result_count,
            )

        # ---------------------------------------------------------------------
        # 5. Build, sign and broadcast transaction
        #
        # IMPORTANT:
        # The lock prevents concurrent Flask requests from using the same
        # pending nonce.
        # ---------------------------------------------------------------------

        with self._tx_lock:

            nonce = self._w3.eth.get_transaction_count(
                self._account.address,
                "pending",
            )
            tx = func.build_transaction(
                {
                    "chainId": self._w3.eth.chain_id,
                    "gas": 300_000,
                    "gasPrice": self._w3.eth.gas_price,
                    "nonce": nonce,
                    "from": self._account.address,
                }
            )

            # Sign locally.
            signed = self._account.sign_transaction(tx)

            # Broadcast signed transaction.
            tx_hash = self._w3.eth.send_raw_transaction(
                signed.raw_transaction
            )

            tx_hash_hex = tx_hash.hex()

        # ---------------------------------------------------------------------
        # 6. Print transaction hash
        # ---------------------------------------------------------------------

        print()
        print("========== POLYGON TRANSACTION ==========")
        print(f"Transaction Hash : {tx_hash_hex}")
        print(f"Subject ID       : {subject_id}")
        print(f"Nonce            : {nonce}")
        print("Status           : Submitted")
        print("==========================================")
        print()

        logger.info(
            "On-chain record submitted: subject=%s tx=%s nonce=%s",
            subject_id,
            tx_hash_hex,
            nonce,
        )

        # ---------------------------------------------------------------------
        # 7. Wait for Polygon confirmation
        # ---------------------------------------------------------------------

        receipt = self._w3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=120,
            poll_latency=0.5,
        )

        # ---------------------------------------------------------------------
        # 8. Check transaction status
        #
        # status == 1 -> success
        # status == 0 -> reverted
        # ---------------------------------------------------------------------

        if receipt["status"] != 1:

            print()
            print("========== POLYGON FAILED ==========")
            print(f"Subject ID       : {subject_id}")
            print(f"Transaction Hash : {tx_hash_hex}")
            print(f"Block Number     : {receipt.get('blockNumber')}")
            print(f"Status           : FAILED / REVERTED")
            print("====================================")
            print()

            raise RuntimeError(
                "On-chain record transaction reverted: "
                f"subject={subject_id}, "
                f"tx={tx_hash_hex}"
            )

        # ---------------------------------------------------------------------
        # 9. Print successful confirmation
        # ---------------------------------------------------------------------

        print()
        print("========== POLYGON CONFIRMED ==========")
        print(f"Subject ID       : {subject_id}")
        print(f"Record Hash      : 0x{record_hash.hex()}")
        print(f"Transaction Hash : {tx_hash_hex}")
        print(f"Block Number     : {receipt['blockNumber']}")
        print(f"Gas Used         : {receipt['gasUsed']}")
        print("Status           : SUCCESS")
        print("========================================")
        print()

        logger.info(
            "On-chain record confirmed: subject=%s tx=%s block=%s gas_used=%s",
            subject_id,
            tx_hash_hex,
            receipt["blockNumber"],
            receipt["gasUsed"],
        )

        # ---------------------------------------------------------------------
        # 10. Return transaction hash to verification service
        # ---------------------------------------------------------------------

        return tx_hash_hex

    # -------------------------------------------------------------------------
    # QUERIES
    # -------------------------------------------------------------------------

    def get_record_hash(
        self,
        subject_id: str,
    ) -> Optional[str]:
        """
        Return the on-chain record hash for a subject.

        Returns:
            Hexadecimal hash with 0x prefix, or None if no record exists.
        """

        self._ensure_web3()

        try:
            raw = self._contract.functions.getRecord(
                subject_id
            ).call()

        except Exception:
            return None

        # Solidity bytes32 zero value means no record.
        if raw == b"\x00" * 32:
            return None

        return "0x" + raw.hex()

    def get_record_with_local_block_hash(
        self,
        subject_id: str,
    ) -> Optional[tuple[str, str]]:
        """
        Return both the on-chain record hash and the attached local block hash.

        Returns:
            A 2-tuple of (recordHash, localBlockHash), both with 0x prefix, or
            None if no record exists. ``localBlockHash`` is the zero bytes32 when
            no local block hash has been attached to this subject's on-chain record.
        """

        self._ensure_web3()

        try:
            record_hash, local_block_hash = self._contract.functions.getRecord(
                subject_id,
                True,
            ).call()

        except Exception:
            return None

        if record_hash == b"\x00" * 32:
            return None

        return (
            "0x" + record_hash.hex(),
            "0x" + local_block_hash.hex(),
        )

    def get_record_local_block_hash(
        self,
        subject_id: str,
    ) -> Optional[str]:
        """
        Legacy single-field accessor for the on-chain local block hash.

        Prefer ``get_record_with_local_block_hash`` when both fields are needed.
        """

        pair = self.get_record_with_local_block_hash(subject_id)
        if pair is None:
            return None

        return pair[1]
    def verify_record(
        self,
        subject_id: str,
        expected_hash_utf8: str,
    ) -> bool:
        """
        Return True when the on-chain record hash matches expected_hash_utf8.

        Args:
            subject_id:
                Subject identifier used when the record was created.

            expected_hash_utf8:
                Keccak-256 hash in hexadecimal form, with or without 0x.

        Returns:
            True if the hashes match.

        Raises:
            ValueError:
                If the supplied hash is invalid or not exactly 32 bytes.

            RuntimeError:
                If the blockchain call fails.
        """

        self._ensure_web3()

        if not expected_hash_utf8:
            raise ValueError(
                "expected_hash_utf8 is required"
            )

        # Remove optional 0x prefix.
        hash_hex = expected_hash_utf8.removeprefix(
            "0x"
        )

        try:
            expected_bytes32 = bytes.fromhex(
                hash_hex
            )

        except ValueError as exc:
            raise ValueError(
                "expected_hash_utf8 must be a valid hexadecimal hash"
            ) from exc

        # bytes32 = exactly 32 bytes.
        if len(expected_bytes32) != 32:
            raise ValueError(
                "expected_hash_utf8 must represent exactly "
                f"32 bytes; got {len(expected_bytes32)} bytes"
            )

        try:
            return bool(
                self._contract.functions.verifyRecord(
                    subject_id,
                    expected_bytes32,
                ).call()
            )

        except Exception as exc:
            raise RuntimeError(
                "Failed to verify record for subject "
                f"'{subject_id}'"
            ) from exc

    def record_count(self) -> int:
        """Return the total number of records created on-chain."""

        self._ensure_web3()

        return int(
            self._contract.functions.recordCount().call()
        )

    def last_record_at(self) -> int:
        """Return the Unix timestamp of the most recently created record."""

        self._ensure_web3()

        return int(
            self._contract.functions.lastRecordAt().call()
        )

    def last_record_by(self) -> str:
        """Return the address that created the most recent record."""

        self._ensure_web3()

        return self._contract.functions.lastRecordBy().call()