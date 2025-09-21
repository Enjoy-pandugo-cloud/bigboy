import { initLucid } from './lucidClient'

function hexFromBytes(bytes){
  return Array.from(bytes).map(b=>b.toString(16).padStart(2,'0')).join('')
}

/**
 * Mint a single NFT to the connected wallet address.
 * This function attempts to use Lucid with a wallet-based policy so the user's wallet
 * signs the minting policy (no server private keys required).
 *
 * Note: Lucid API surface can change between versions. If you see runtime errors,
 * you may need to adjust calls like `newPolicyFromWallet` or how `mintAssets` is attached.
 */
export async function mintCertificateNFT(blockfrostKey, tokenName, metadata = {}){
  const lucid = await initLucid(blockfrostKey)

  // Owner address
  const ownerAddr = await lucid.wallet.address()

  // Create a wallet-based policy (the user's wallet will sign the policy)
  // Lucid provides helpers to create policies from wallet; use whichever API is available in your Lucid version.
  let policy
  // Try common policy creation helpers in order
  try{
    if(typeof lucid.newPolicyFromWallet === 'function'){
      policy = await lucid.newPolicyFromWallet()
      console.debug('policy created via newPolicyFromWallet')
    }
  }catch(e){
    console.debug('newPolicyFromWallet failed', e)
  }

  if(!policy){
    try{
      if(typeof lucid.newPolicy === 'function'){
        // newPolicy expects a signing function that will be invoked by Lucid when signing the tx
        policy = await lucid.newPolicy(async (tx)=>{
          // Lucid will handle wallet signing during tx.sign(); keep this as a no-op stub
          return {}
        })
        console.debug('policy created via newPolicy')
      }
    }catch(e){
      console.debug('newPolicy attempt failed', e)
    }
  }

  if(!policy){
    // If no programmatic policy is available, try to build a temporary policy structure
    // Some Lucid versions expose policy.id on other helpers - try to find an ID
    if(lucid.utils && typeof lucid.utils.createPolicy === 'function'){
      try{
        policy = lucid.utils.createPolicy()
        console.debug('policy created via lucid.utils.createPolicy')
      }catch(e){
        console.debug('lucid.utils.createPolicy failed', e)
      }
    }
  }

  if(!policy){
    throw new Error('Could not create a wallet-backed policy with your Lucid version. Please check lucid-cardano version and that the wallet supports signing policy scripts.')
  }

  const policyId = policy.id || policy.policyId || policy.hex || policy.policyIdHex || ''

  // Token name bytes -> hex
  const encoder = new TextEncoder()
  const tokenNameHex = Array.from(encoder.encode(tokenName)).map(b=>b.toString(16).padStart(2,'0')).join('')
  const unit = policyId + tokenNameHex

  // Prepare CIP-721 / 721 metadata (CIP-25 uses 721)
  const metadata721 = {
    [policyId]: {
      [tokenName]: {
        name: tokenName,
        ...metadata
      }
    }
  }

  // Build, mint, sign, and submit tx
  // Build the tx; Lucid will include the policy witness when signing
  const tx = await lucid.newTx()
    .mintAssets({ [unit]: 1n })
    .payToAddress(ownerAddr, { [unit]: 1n })
    .attachMetadata(721, metadata721)
    .complete()

  const signed = await tx.sign().complete()

  // get signed tx hex - try common Lucid methods
  let signedHex = null
  if(signed && typeof signed.to_hex === 'function'){
    signedHex = await signed.to_hex()
  } else if(signed && typeof signed.to_bytes === 'function'){
    const bytes = await signed.to_bytes()
    signedHex = hexFromBytes(bytes)
  } else if(typeof signed === 'string'){
    signedHex = signed
  }

  if(!signedHex) throw new Error('Could not extract signed tx hex from Lucid transaction object; check Lucid version and wallet support')

  const txHash = await lucid.submitTx(signedHex)

  return { txHash, policyId, unit, tokenName }
}
