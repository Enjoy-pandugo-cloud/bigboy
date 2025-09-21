import os
import httpx
import logging

logger = logging.getLogger(__name__)

BLOCKFROST_BASE = "https://cardano-preprod.blockfrost.io/api/v0"
BLOCKFROST_API_KEY = os.getenv("BLOCKFROST_API_KEY")


async def verify_transaction_pay_to_address(tx_hash: str, seller_address: str, min_lovelace: int) -> dict:
    """Verify that a transaction with tx_hash contains at least min_lovelace sent to seller_address.

    Returns a dict with keys: ok (bool), details (dict)
    """
    headers = {"project_id": BLOCKFROST_API_KEY}
    async with httpx.AsyncClient(timeout=20.0) as client:
        # Get UTXO outputs for the transaction
        url = f"{BLOCKFROST_BASE}/txs/{tx_hash}/utxos"
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Error fetching tx utxos from Blockfrost: {e}")
            return {"ok": False, "details": {"error": str(e)}}

        data = resp.json()
        # data contains 'outputs' list
        outputs = data.get("outputs", [])
        received = 0
        matching_outputs = []
        for out in outputs:
            addr = out.get("address")
            if addr == seller_address:
                # sum amount entries of unit lovelace
                for amt in out.get("amount", []):
                    if amt.get("unit") == "lovelace":
                        value = int(amt.get("quantity", "0"))
                        received += value
                        matching_outputs.append({"address": addr, "value": value})

        ok = received >= min_lovelace
        return {"ok": ok, "details": {"received": received, "matching_outputs": matching_outputs, "required": min_lovelace}}
