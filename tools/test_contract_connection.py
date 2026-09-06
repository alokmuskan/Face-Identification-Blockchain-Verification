from blockchain.contract import ContractBridge
import config_chain


bridge = ContractBridge(
    rpc_url=config_chain.POLY_AMOY_RPC,
    contract_address=config_chain.CONTRACT_ADDRESS,
    private_key=config_chain.PRIVATE_KEY,
    chain_id=config_chain.CHAIN_ID,
)

print("Connected successfully!")
print("Contract:", config_chain.CONTRACT_ADDRESS)
print("Chain ID:", config_chain.CHAIN_ID)
print("Record count:", bridge.record_count())
print("Last record:", bridge.last_record_at())
print("Last writer:", bridge.last_record_by())