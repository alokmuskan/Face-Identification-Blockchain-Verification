#!/usr/bin/env python
# Submit a face-verification record to the on-chain FaceVerificationHub on Polygon Amoy.
#
# Usage (after deploying the contract via Remix):
#   python tools/contract.py submit \
#       --subject-id barack-obama-ee8f7c \
#       --similarity 1.0 \
#       --result VERIFIED \
#       --probe-image-hash 744dd848fbb0584229169e01c4944664957c62495fb9e8af514a088ebca43e19 \
#       --web-result-count 10
#
# Configuration is read from a local config file that is NOT committed to version
# control. Copy config_chain.example.py to config_chain.py, fill in the values, and
# keep config_chain.py out of the repo.
import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- load config
try:
    import config_chain  # type: ignore[import]  # noqa: F401
except ModuleNotFoundError:
    print(
        "No local config_chain.py found. Copy config_chain.example.py to config_chain.py, "
        "fill in the deployed contract address and a funded wallet private key, then rerun.",
        file=sys.stderr,
    )
    sys.exit(2)

from blockchain.contract import ContractBridge, compute_record_hash

EXAMPLE_CONFIG = """
# Copy this file to config_chain.py and fill in the values.
# Do NOT commit config_chain.py to version control.

# Polygon Amoy RPC (public, no key needed for basic use).
POLY_AMOY_RPC = "https://rpc-amoy.polygon.technology"

# The deployed FaceVerificationHub contract address (from Remix).
CONTRACT_ADDRESS = ""

# A funded wallet private key (Hex without 0x prefix or with 0x prefix both work).
# NEVER commit this file with a real key.
PRIVATE_KEY = ""

# Polygon Amoy chain id.
CHAIN_ID = 80002
"""


def _ensure_example_config() -> None:
    example = Path(__file__).resolve().parent / "config_chain.example.py"
    if not example.exists():
        example.write_text(EXAMPLE_CONFIG, encoding="utf-8")
        logger.info("Wrote %s", example)


def _submit(args: argparse.Namespace) -> None:
    bridge = ContractBridge(
        rpc_url=config_chain.POLY_AMOY_RPC,
        contract_address=config_chain.CONTRACT_ADDRESS,
        private_key=config_chain.PRIVATE_KEY,
        chain_id=getattr(config_chain, "CHAIN_ID", 80002),
    )
    tx_hash = bridge.submit_record(
        subject_id=args.subject_id,
        similarity=args.similarity,
        result=args.result,
        probe_image_hash=args.probe_image_hash,
        web_result_count=args.web_count,
    )
    # The canonical on-chain record hash is keccak256 of the payload bytes.
    # compute_record_hash() produces the exact same value the contract stores.
    local_record_hash = compute_record_hash(
        subject_id=args.subject_id,
        similarity=args.similarity,
        result=args.result,
        probe_image_hash=args.probe_image_hash,
        web_result_count=args.web_count,
    )
    print("On-chain tx hash:", tx_hash)
    print("Polygonscan link: https://amoy.polygonscan.com/tx/" + tx_hash)
    print("Local record hash (keccak256 of payload, should equal on-chain recordHash):")
    print("  ", local_record_hash)
    print("On-chain recordHash:")
    on_chain_hash = bridge.get_record_hash(args.subject_id)
    print("  ", on_chain_hash)
    print("Cross-check (local == on-chain):", local_record_hash == (on_chain_hash or ""))
    print(
        "If the line above is True, the on-chain record is bound to this exact local payload."
    )


def _verify(args: argparse.Namespace) -> None:
    bridge = ContractBridge(
        rpc_url=config_chain.POLY_AMOY_RPC,
        contract_address=config_chain.CONTRACT_ADDRESS,
        private_key=config_chain.PRIVATE_KEY,
        chain_id=getattr(config_chain, "CHAIN_ID", 80002),
    )
    on_chain = bridge.get_record_hash(args.subject_id)
    if on_chain is None:
        print(f"No on-chain record for subject {args.subject_id}")
        sys.exit(1)
    print("On-chain recordHash:", on_chain)
    print("On-chain recordCount:", bridge.record_count())
    print("On-chain lastRecordAt:", bridge.last_record_at())
    print("On-chain lastRecordBy:", bridge.last_record_by())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interact with FaceVerificationHub on Polygon Amoy."
    )
    sub = parser.add_subparsers(dest="command")

    p_submit = sub.add_parser("submit", help="Submit a record on-chain.")
    p_submit.add_argument("--subject-id", required=True)
    p_submit.add_argument("--similarity", type=float, required=True)
    p_submit.add_argument("--result", required=True)
    p_submit.add_argument("--probe-image-hash", required=True)
    p_submit.add_argument("--web-count", type=int, required=True)

    p_verify = sub.add_parser("verify", help="Read the on-chain record for a subject.")
    p_verify.add_argument("--subject-id", required=True)

    p_example = sub.add_parser("example-config", help="Write config_chain.example.py.")

    args = parser.parse_args()
    if args.command == "submit":
        _submit(args)
    elif args.command == "verify":
        _verify(args)
    elif args.command == "example-config":
        _ensure_example_config()
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
