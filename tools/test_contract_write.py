from blockchain.contract import ContractBridge
import config_chain


bridge = ContractBridge(
    rpc_url=config_chain.POLY_AMOY_RPC,
    contract_address=config_chain.CONTRACT_ADDRESS,
    private_key=config_chain.PRIVATE_KEY,
    chain_id=config_chain.CHAIN_ID,
)

tx_hash = bridge.submit_record(
    subject_id="test-user-001",
    similarity=0.95,
    result="VERIFIED",
    probe_image_hash="test-image-hash",
    web_result_count=0,
)

print("Transaction submitted!")
print("Transaction hash:", tx_hash)