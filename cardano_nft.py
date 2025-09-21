import os
import logging

logger = logging.getLogger(__name__)

def mint_certificate_nft_mock(owner_address: str, metadata: dict) -> dict:
    """Mock minting function for a certificate NFT.

    This is a placeholder for the hackathon. Full minting requires Lucid or Blockfrost + key management.
    We return a simulated policy id and token name and include instructions for how to mint with Lucid.
    """
    policy_id = os.getenv("MOCK_POLICY_ID", "mockpolicy1234567890")
    token_name = f"Certificate-{metadata.get('job_id','unknown')}"
    logger.info(f"(mock) Minted NFT {policy_id}.{token_name} for {owner_address}")
    return {"policy_id": policy_id, "token_name": token_name, "owner": owner_address, "metadata": metadata}
