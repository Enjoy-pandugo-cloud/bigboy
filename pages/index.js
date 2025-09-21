import {useState, useEffect} from 'react'
import axios from 'axios'
import { initLucid, payAndSubmit } from '../lib/lucidClient'
import { mintCertificateNFT } from '../lib/mintClient'

export default function Home(){
  const [query, setQuery] = useState('Write a polite follow-up email about our meeting')
  const [job, setJob] = useState(null)
  const [tx, setTx] = useState('')
  const [result, setResult] = useState(null)
  const [yoroiAvailable, setYoroiAvailable] = useState(false)
  const [yoroiApi, setYoroiApi] = useState(null)
  const [walletAddr, setWalletAddr] = useState(null)

  // detect yoroi
  const detectYoroi = () => {
    const cardano = (typeof window !== 'undefined') ? window.cardano : null
    if(cardano && cardano.yoroi){
      setYoroiAvailable(true)
    }
  }

  // connect / enable yoroi
  const connectYoroi = async ()=>{
    try{
      const api = await window.cardano.yoroi.enable()
      setYoroiApi(api)
      // get first used address (CIP-30 returns hex addresses)
      const used = await api.getUsedAddresses()
      if(used && used.length>0){
        // addresses are hex, we present them as-is; user can copy
        setWalletAddr(used[0])
      }
    }catch(e){
      alert('Could not connect to Yoroi: '+e)
    }
  }

  const startJob = async ()=>{
    const payload = {identifier_from_purchaser: walletAddr || 'web_user_1', input_data: {text: query}}
    const res = await axios.post('http://localhost:8000/start_job', payload)
    setJob(res.data)
  }

  const payWithYoroi = async ()=>{
    if(!job) return alert('Start job first')
    try{
      const blockfrostKey = process.env.NEXT_PUBLIC_BLOCKFROST || ''
      if(!blockfrostKey) return alert('Set NEXT_PUBLIC_BLOCKFROST env in frontend to your Blockfrost Preprod key')
      const lucid = await initLucid(blockfrostKey)
      const txHash = await payAndSubmit(lucid, job.seller_address, job.required_lovelace)
      // Submit tx hash to backend
      await axios.post('http://localhost:8000/submit_tx', null, {params: {job_id: job.job_id, tx_hash: txHash}})
      // Mint a certificate NFT to the purchaser
      try{
        const mintRes = await mintCertificateNFT(blockfrostKey, `certificate-${job.job_id}`, { job_id: job.job_id, purchaser: walletAddr || 'unknown' })
        console.log('Mint result', mintRes)
        setResult(prev => ({...prev, nft: mintRes}))
      }catch(me){
        console.warn('Mint failed', me)
      }
      // Poll status
      setTimeout(async ()=>{
        const status = await axios.get('http://localhost:8000/status', {params: {job_id: job.job_id}})
        setResult(status.data)
      }, 4000)
    }catch(e){
      alert('Payment failed: '+e)
    }
  }

  const submitTx = async ()=>{
    if(!job || !job.job_id) return alert('No job')
    const res = await axios.post('http://localhost:8000/submit_tx', null, {params: {job_id: job.job_id, tx_hash: tx}})
    setResult(res.data)
    // poll status
    setTimeout(async ()=>{
      const status = await axios.get('http://localhost:8000/status', {params: {job_id: job.job_id}})
      setResult(status.data)
    }, 4000)
  }

  // detect on client after mount to avoid SSR hydration mismatch
  useEffect(()=>{
    detectYoroi()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div style={{padding:20}}>
      <h1>CrewAI + Cardano (Preprod) MVP</h1>

      <div style={{marginBottom:10}}>
        {yoroiAvailable ? (
          <>
            <button onClick={connectYoroi}>Connect Yoroi Wallet</button>
            {walletAddr && <div style={{marginTop:8}}>Connected address (hex): <code>{walletAddr}</code></div>}
          </>
        ) : (
          <div>Yoroi wallet not detected in browser. Install Yoroi or use a compatible wallet extension.</div>
        )}
      </div>

      <textarea value={query} onChange={e=>setQuery(e.target.value)} rows={6} cols={80} />
      <div style={{marginTop:10}}>
        <button onClick={startJob}>Start Paid Job (gets payment instructions)</button>
      </div>

      {job && (
        <div style={{marginTop:20}}>
          <h3>Payment Instructions</h3>
          <p>Send required lovelace to: <b>{job.seller_address}</b></p>
          <p>Required (lovelace): <b>{job.required_lovelace}</b></p>
          <p>Click the button below to pay with Yoroi (Preprod). The signed tx will be submitted and the tx hash posted back to the backend automatically.</p>
          <div style={{marginTop:8}}>
            <button onClick={payWithYoroi}>Pay with Yoroi</button>
          </div>
          <hr />
          <p>Or paste the tx hash manually:</p>
          <input value={tx} onChange={e=>setTx(e.target.value)} style={{width:600}} />
          <div style={{marginTop:8}}>
            <button onClick={submitTx}>Submit Tx Hash</button>
          </div>
        </div>
      )}

      {result && (
        <div style={{marginTop:20}}>
          <h3>Result</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
