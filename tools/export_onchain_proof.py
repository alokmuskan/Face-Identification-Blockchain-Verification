#!/usr/bin/env python
# Print the full Phase 3 proof fields for a submitted subject.
#
# This is meant to be run during a demo or before submission so the exact
# local payload, on-chain record, and traceability linkage can be printed
# in one place.
#
# Configuration is read from a local config file that is NOT committed to
# version control. Copy config_chain.example.py to config_chain.py, fill in
# the values, and keep config_chain.py out of the repo.
import argparse
import sys
from pathlib import Path

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
from services.verification_service import VerificationService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print the full on-chain + local proof fields for a subject.",
    )
    parser.add_argument("--subject-id", required=True)
    args = parser.parse_args()

    service = VerificationService()
    bridge = ContractBridge(
        rpc_url=config_chain.POLY_AMOY_RPC,
        contract_address=config_chain.CONTRACT_ADDRESS,
        private_key=config_chain.PRIVATE_KEY,
        chain_id=getattr(config_chain, "CHAIN_ID", 80002),
    )

    report = service.verify_contract(args.subject_id)
    if not report.get("ok"):
        print("Proof unavailable:", report.get("error"))
        sys.exit(1)

    # Latest local FACE_VERIFICATION transaction for this subject.
    events = service.blockchain.transactions_for_subject(args.subject_id)
    verif = None
    for ev in reversed(events):
        if ev.get("type") == "FACE_VERIFICATION":
            verif = ev
            break

    print()
    print("========== PHASE 3 PROOF ==========")
    print(f"Subject ID            : {report['subject_id']}")
    print(f"Local record hash     : {report['local_record_hash']}")
    print(f"On-chain record hash  : {report['on_chain_record_hash']}")
    print(f"Local == on-chain     : {report['local_record_hash'] == report['on_chain_record_hash']}")
    print(f"On-chain match        : {report['on_chain_match']}")
    print()
    print("Traceability (local <-> on-chain):")
    print(f"  Local block index           : {report.get('local_block_index') or '—'}")
    print(f"  Local block hash            : {report.get('local_block_hash') or '—'}")
    print(f"  On-chain local block hash   : {report.get('on_chain_local_block_hash') or '—'}")
    print(f"  Local block hash matches   : {report.get('local_block_hash_matches_on_chain') or '—'}")
    print()
    print("On-chain transaction:")
    print(f"  Contract tx hash   : {report.get('contract_tx_hash') or '—'}")
    print(f"  Contract chain     : {report.get('contract_chain') or 'polygon-amoy'}")
    if report.get("contract_tx_hash") and config_chain.CONTRACT_ADDRESS:
        print("  Polygonscan tx     : https://amoy.polygonscan.com/tx/" + report["contract_tx_hash"])
        print("  Polygonscan contract: https://amoy.polygonscan.com/address/" + config_chain.CONTRACT_ADDRESS)
    print("====================================")
    print()

    if verif:
        print("Local payload fields (from ledger):")
        for key in (
            "type",
            "result",
            "subject_id",
            "subject_name",
            "similarity",
            "probe_image_hash",
            "web_search_count",
            "contract_tx_hash",
            "contract_chain",
            "local_block_hash",
            "block_index",
            "block_hash",
        ):
            print(f"  {key}: {verif.get(key) or '—'}")
        print()

        # Recompute the canonical record hash from the local payload so the
        # export itself is reproducible and self-checking.
        recomputed = compute_record_hash(
            subject_id=verif.get("subject_id", args.subject_id),
            similarity=verif.get("similarity", 0.0),
            result=verif.get("result", ""),
            probe_image_hash=verif.get("probe_image_hash", ""),
            web_result_count=verif.get("web_search_count", 0),
            local_block_hash=verif.get("local_block_hash", ""),
        )
        print("Reproducibility check:")
        print(f"  recomputed local record hash : {recomputed}")
        print(f"  matches reported local hash  : {recomputed == report['local_record_hash']}")
    print()


if __name__ == "__main__":
    main()
