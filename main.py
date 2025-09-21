import os
import uvicorn
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from masumi.config import Config
from masumi.payment import Payment, Amount
from crew_definition import ResearchCrew
from cardano_payments import verify_transaction_pay_to_address
from cardano_nft import mint_certificate_nft_mock
from logging_config import setup_logging

# Configure logging
logger = setup_logging()

# Load environment variables
load_dotenv(override=True)

# Retrieve API Keys and URLs
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL")
PAYMENT_API_KEY = os.getenv("PAYMENT_API_KEY")
NETWORK = os.getenv("NETWORK")

logger.info("Starting application with configuration:")
logger.info(f"PAYMENT_SERVICE_URL: {PAYMENT_SERVICE_URL}")

# Initialize FastAPI
app = FastAPI(
    title="API following the Masumi API Standard",
    description="API for running Agentic Services tasks with Masumi payment integration",
    version="1.0.0"
)

# Allow CORS for frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Temporary in-memory job store (DO NOT USE IN PRODUCTION)
# ─────────────────────────────────────────────────────────────────────────────
jobs = {}
payment_instances = {}
tx_logs = {}

# ─────────────────────────────────────────────────────────────────────────────
# Initialize Masumi Payment Config
# ─────────────────────────────────────────────────────────────────────────────
config = Config(
    payment_service_url=PAYMENT_SERVICE_URL,
    payment_api_key=PAYMENT_API_KEY
)

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────
class StartJobRequest(BaseModel):
    identifier_from_purchaser: str
    input_data: dict[str, str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "identifier_from_purchaser": "example_purchaser_123",
                "input_data": {
                    "text": "Write a story about a robot learning to paint"
                }
            }
        }

class ProvideInputRequest(BaseModel):
    job_id: str

# ─────────────────────────────────────────────────────────────────────────────
# CrewAI Task Execution
# ─────────────────────────────────────────────────────────────────────────────
async def execute_crew_task(input_data: str) -> str:
    """ Execute a CrewAI task with Research and Writing Agents """
    logger.info(f"Starting CrewAI task with input: {input_data}")
    crew = ResearchCrew(logger=logger)
    # If input_data is a dict with task_type, pass through, else assume text
    if isinstance(input_data, dict):
        inputs = input_data
    else:
        inputs = {"text": input_data}
    # Decide task type
    task_type = inputs.get("task_type", "reply")
    # Map task types to simple prompts
    if task_type == "research":
        prompt = inputs.get("text", "")
        result = crew.crew.kickoff(inputs={"text": prompt, "task": "research"})
    elif task_type == "summarize":
        prompt = inputs.get("text", "")
        result = crew.crew.kickoff(inputs={"text": prompt, "task": "summarize"})
    else:
        # default to reply/draft creation
        prompt = inputs.get("text", "")
        result = crew.crew.kickoff(inputs={"text": prompt, "task": "reply"})
    logger.info("CrewAI task completed successfully")
    return result

# ─────────────────────────────────────────────────────────────────────────────
# 1) Start Job (MIP-003: /start_job)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/force_run")
async def force_run(data:StartJobRequest):
    result = await execute_crew_task(data.input_data.get("text")) 
    return result

@app.post("/start_job")
async def start_job(data: StartJobRequest):
    """ Initiates a job and creates a payment request """
    print(f"Received data: {data}")
    print(f"Received data.input_data: {data.input_data}")
    try:
        job_id = str(uuid.uuid4())
        agent_identifier = os.getenv("AGENT_IDENTIFIER")
        
        # Log the input text (truncate if too long)
        input_text = data.input_data["text"]
        truncated_input = input_text[:100] + "..." if len(input_text) > 100 else input_text
        logger.info(f"Received job request with input: '{truncated_input}'")
        logger.info(f"Starting job {job_id} with agent {agent_identifier}")

        # For hackathon MVP we'll accept an off-chain tx proof: purchaser submits tx_hash after sending test ADA
        jobs[job_id] = {
            "status": "awaiting_payment",
            "payment_status": "pending",
            "tx_hash": None,
            "input_data": data.input_data,
            "result": None,
            "identifier_from_purchaser": data.identifier_from_purchaser
        }

        return {
            "status": "pending_payment",
            "job_id": job_id,
            "message": "Send a small ADA payment to the seller address and POST /submit_tx with tx_hash",
            "seller_address": os.getenv("SELLER_ADDRESS"),
            "required_lovelace": int(os.getenv("PAYMENT_AMOUNT", "10000000"))
        }
    except KeyError as e:
        logger.error(f"Missing required field in request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Bad Request: If input_data or identifier_from_purchaser is missing, invalid, or does not adhere to the schema."
        )
    except Exception as e:
        logger.error(f"Error in start_job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Input_data or identifier_from_purchaser is missing, invalid, or does not adhere to the schema."
        )

# ─────────────────────────────────────────────────────────────────────────────
# 2) Process Payment and Execute AI Task
# ─────────────────────────────────────────────────────────────────────────────
async def handle_payment_status(job_id: str, payment_id: str) -> None:
    """ Executes CrewAI task after payment confirmation.

    payment_id may be a Masumi payment id or a Cardano tx hash (off-chain proof).
    The function is resilient if no masumi payment instance exists for the job.
    """
    try:
        logger.info(f"Payment {payment_id} completed for job {job_id}, executing task...")

        # Update job status to running
        jobs[job_id]["status"] = "running"
        logger.info(f"Input data: {jobs[job_id]['input_data']}")

        # Execute the AI task
        result = await execute_crew_task(jobs[job_id]["input_data"])
        # Attempt to extract a serializable dict if available
        try:
            result_dict = getattr(result, "json_dict", None) or getattr(result, "raw", None) or str(result)
        except Exception:
            result_dict = str(result)

        logger.info(f"Crew task completed for job {job_id}")

        # If there is a Masumi payment instance, mark payment completed on Masumi
        if job_id in payment_instances:
            try:
                await payment_instances[job_id].complete_payment(payment_id, result_dict)
                logger.info(f"Masumi payment completed for job {job_id}")
            except Exception as e:
                logger.warning(f"Could not complete Masumi payment for {job_id}: {e}")

        # Update job status
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["payment_status"] = "completed"
        jobs[job_id]["result"] = result

        # store tx log if present
        if job_id in tx_logs:
            jobs[job_id]["tx"] = tx_logs.get(job_id)

        # Bonus: mint simple certificate NFT (mock)
        try:
            owner = os.getenv("CERT_OWNER_ADDRESS") or tx_logs.get(job_id, {}).get('verified', {}).get('address')
            metadata = {"job_id": job_id, "identifier": jobs[job_id].get("identifier_from_purchaser")}
            nft = mint_certificate_nft_mock(owner or "unknown", metadata)
            jobs[job_id]["nft"] = nft
        except Exception as e:
            logger.warning(f"Could not mint mock NFT for job {job_id}: {e}")

        # Stop monitoring payment status if present
        if job_id in payment_instances:
            try:
                payment_instances[job_id].stop_status_monitoring()
            except Exception:
                pass
            del payment_instances[job_id]
    except Exception as e:
        logger.error(f"Error processing payment {payment_id} for job {job_id}: {str(e)}", exc_info=True)
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

        # Still stop monitoring to prevent repeated failures
        if job_id in payment_instances:
            try:
                payment_instances[job_id].stop_status_monitoring()
            except Exception:
                pass
            del payment_instances[job_id]

# ─────────────────────────────────────────────────────────────────────────────
# 3) Check Job and Payment Status (MIP-003: /status)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/status")
async def get_status(job_id: str):
    """ Retrieves the current status of a specific job """
    logger.info(f"Checking status for job {job_id}")
    if job_id not in jobs:
        logger.warning(f"Job {job_id} not found")
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # Check latest payment status if payment instance exists
    if job_id in payment_instances:
        try:
            status = await payment_instances[job_id].check_payment_status()
            job["payment_status"] = status.get("data", {}).get("status")
            logger.info(f"Updated payment status for job {job_id}: {job['payment_status']}")
        except ValueError as e:
            logger.warning(f"Error checking payment status: {str(e)}")
            job["payment_status"] = "unknown"
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}", exc_info=True)
            job["payment_status"] = "error"


    result_data = job.get("result")
    result = result_data.raw if result_data and hasattr(result_data, "raw") else None

    return {
        "job_id": job_id,
        "status": job["status"],
        "payment_status": job["payment_status"],
        "result": result,
        "tx": job.get("tx")
    }


@app.post("/submit_tx")
async def submit_tx(job_id: str = Query(...), tx_hash: str = Query(...)):
    """Submit a Blockfrost tx hash proof for a job. This will verify funds were sent to SELLER_ADDRESS on Preprod."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    seller_address = os.getenv("SELLER_ADDRESS")
    if not seller_address:
        raise HTTPException(status_code=500, detail="SELLER_ADDRESS not configured on server")

    required = int(os.getenv("PAYMENT_AMOUNT", "10000000"))
    # Verify via Blockfrost
    verification = await verify_transaction_pay_to_address(tx_hash, seller_address, required)
    if not verification.get("ok"):
        jobs[job_id]["payment_status"] = "failed"
        jobs[job_id]["status"] = "failed"
        return {"status": "failed", "details": verification}

    # mark job paid and store tx
    jobs[job_id]["payment_status"] = "completed"
    jobs[job_id]["tx_hash"] = tx_hash
    tx_logs[job_id] = {"tx_hash": tx_hash, "verified": verification.get("details")}

    # Execute the AI task in background
    import asyncio
    asyncio.create_task(handle_payment_status(job_id, tx_hash))

    return {"status": "accepted", "job_id": job_id, "tx_hash": tx_hash, "verification": verification}

# ─────────────────────────────────────────────────────────────────────────────
# 4) Check Server Availability (MIP-003: /availability)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/availability")
async def check_availability():
    """ Checks if the server is operational """

    return {"status": "available", "type": "masumi-agent", "message": "Server operational."}
    # Commented out for simplicity sake but its recommended to include the agentIdentifier
    #return {"status": "available","agentIdentifier": os.getenv("AGENT_IDENTIFIER"), "message": "The server is running smoothly."}

# ─────────────────────────────────────────────────────────────────────────────
# 5) Retrieve Input Schema (MIP-003: /input_schema)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/input_schema")
async def input_schema():
    """
    Returns the expected input schema for the /start_job endpoint.
    Fulfills MIP-003 /input_schema endpoint.
    """
    return {
        "input_data": [
            {
                "id": "text",
                "type": "string",
                "name": "Task Description",
                "data": {
                    "description": "The text input for the AI task",
                    "placeholder": "Enter your task description here"
                }
            }
        ]
    }

# ─────────────────────────────────────────────────────────────────────────────
# 6) Health Check
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """
    Returns the health of the server.
    """
    return {
        "status": "healthy"
    }

# ─────────────────────────────────────────────────────────────────────────────
# Main Logic if Called as a Script
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("Running CrewAI as standalone script is not supported when using payments.")
    print("Start the API using `python main.py api` instead.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "api":
        print("Starting FastAPI server with Masumi integration...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        main()
