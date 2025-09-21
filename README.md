# Crewai Gmail Draft Creator Agent — Hackathon MVP

This repository is a hackathon-ready MVP that combines a CrewAI agent (for Gmail drafts and general queries) with a Cardano Preprod payment gate. The flow: user connects a wallet on the frontend, pays a small ADA amount on Preprod, then the backend verifies the transaction via Blockfrost and runs the AI agent to produce a result (draft, summary, reply). A mock NFT certificate is produced as a bonus.

Repository: git@github.com:Enjoy-pandugo-cloud/bigboy.git

Note: the Masumi repository was used to generate the initial template for this project.

## Quick setup (Windows PowerShell)

1. Copy environment variables:

```powershell
copy .\.env.example .\.env
# then edit .env and fill in BLOCKFROST_API_KEY, OPENAI_API_KEY and SELLER_ADDRESS (preprod address)
```

2. Backend (Python) - create venv and install deps:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

3. Start backend API (port 8000):

```powershell
python main.py api
```

4. Frontend (Next.js) - install and run (port 3001):

```powershell
cd frontend
npm install
npm run dev
```

5. Wallet & payment flow (frontend):

- Connect a Preprod wallet (Begin, Nami, or Yoroi on Preprod). Ensure your wallet is funded with Preprod ADA (faucet).
- Enter your query and initiate the payment. The frontend will create and submit a transaction sending the configured lovelace amount to `SELLER_ADDRESS` and return the txHash.
- The backend accepts `POST /start_job` to create a job, then the frontend or caller should `POST /submit_tx?job_id=...&tx_hash=...` to confirm payment.

## Notes & Implementation Details

- Payments: Backend verifies tx outputs with Blockfrost Preprod using `BLOCKFROST_API_KEY` and `cardano_payments.verify_transaction_pay_to_address`.
- Agent: CrewAI-based crew in `crew_definition.py` exposes research, summarization, and reply tasks. The Gmail tool is in `gmail_tool.py` and uses Google API credentials (`credentials.json`) to create drafts.
- NFT: `cardano_nft.py` currently provides a mock mint function; frontend has Lucid helpers for direct wallet-based minting as a later enhancement.

## Next steps I will perform (progress will be updated):

- Ensure backend runs without missing dependencies and add minor fixes.
- Extend `gmail_tool.py` to provide a generalized agent interface for summaries and replies.
- Wire up a minimal frontend page to connect wallet, call `/start_job`, perform payment via Lucid, then call `/submit_tx` and display the result.

## PPT on the project 
- ("https://drive.google.com/file/d/1Gz3338sAhH-zPjfxIClSjSZvq6yxLref/view?usp=sharing")

## Contact
- archlinuxadithya@gmail.com
- Team Leader - Adithya Srivatsa
- Members - Chetan, Yekeshwar Naik, Sri Krishna Teja and Varshith

- illu em cheyale, motham nene chesa - Adithya.. hahahahaha


