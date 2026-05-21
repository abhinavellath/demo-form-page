from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import requests
import os
from dotenv import load_dotenv

from rag import retrieve_kb_context

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")


class Lead(BaseModel):
    name: str
    phone: str
    role: str
    experience: str


@app.get("/")
async def root():
    return {"message": "Backend running"}


@app.post("/lead")
async def receive_lead(data: Lead):

    print("===== NEW LEAD RECEIVED =====")
    print("Name:", data.name)
    print("Phone:", data.phone)
    print("Role:", data.role)
    print("Experience:", data.experience)
    print("=============================")

    kb_context, rag_meta = retrieve_kb_context(
        role=data.role,
        experience=data.experience,
        name=data.name,
    )
    print("RAG:", json.dumps(rag_meta, default=str))

    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": data.phone,
            "name": data.name
        },
        "assistantOverrides": {
            "variableValues": {
                "candidate_name": data.name,
                "role": data.role,
                "experience": data.experience,
                "kb_context": kb_context,
            }
        }
    }

    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://api.vapi.ai/call",
        json=payload,
        headers=headers
    )

    print(response.text)

    return {
        "message": f"AI recruiter is calling {data.name}"
    }