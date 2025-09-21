import { Lucid, Blockfrost } from 'lucid-cardano'

let lucidInstance = null

export async function initLucid(blockfrostKey) {
  if (lucidInstance) return lucidInstance
  if (!window || !window.cardano || !window.cardano.yoroi) {
    throw new Error('Yoroi wallet not available in window.cardano.yoroi')
  }

  const api = await window.cardano.yoroi.enable()

  // create Lucid instance pointed at Preprod
  const blockfrost = new Blockfrost('https://cardano-preprod.blockfrost.io/api/v0', blockfrostKey)
  const lucid = await Lucid.new(blockfrost, 'Preprod')
  lucid.selectWallet(api)
  lucidInstance = lucid
  return lucid
}

export async function payAndSubmit(lucid, sellerAddress, lovelace) {
  // Build, sign, and submit a simple payment transaction sending lovelace to sellerAddress.
  // Returns txHash on success.
  const amount = BigInt(lovelace)
  const tx = await lucid.newTx().payToAddress(sellerAddress, { lovelace: amount }).complete()
  const signed = await tx.sign().complete()

  // signed may expose to_hex or to_bytes
  let raw
  if (signed.to_hex) {
    raw = await signed.to_hex()
  } else if (signed.to_bytes) {
    const bytes = await signed.to_bytes()
    // convert bytes to hex
    raw = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('')
  } else {
    // fallback: try JSON
    raw = JSON.stringify(signed)
  }

  // submitTx accepts a hex string of the signed tx
  const txHash = await lucid.submitTx(raw)
  return txHash
}
