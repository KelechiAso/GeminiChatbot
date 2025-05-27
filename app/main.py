# app/main.py
print("--- app/main.py: TOP OF FILE (Importing AI Service Test) ---")

from fastapi import FastAPI, HTTPException, Request # Added Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json
import traceback
import pprint

print("--- app/main.py: Standard imports DONE ---")

# Attempt to import from openai_service
try:
    print("--- app/main.py: Attempting to import from api.openai_service ---")
    from api.openai_service import (
        extract_sports_info,
        fetch_raw_text_data,
        get_structured_data_and_reply_via_tools
    )
    print("--- app/main.py: SUCCESSFULLY IMPORTED from api.openai_service ---")
except ImportError as e:
    print(f"--- app/main.py: !!! FAILED to import from api.openai_service: {e} !!! ---")
    # You might want to raise e here or handle it to prevent app startup if critical
    # For now, printing helps diagnose if Railway hides the direct ImportError.
    extract_sports_info = None # Define placeholders so app doesn't crash immediately if not used yet
    fetch_raw_text_data = None
    get_structured_data_and_reply_via_tools = None


app = FastAPI(title="SPAI - Importing AI Service Test")
print("--- app/main.py: FastAPI INSTANCE CREATED ---")

# --- CORS ---
origins = ["*",]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
print("--- app/main.py: CORS Middleware ADDED ---")

# --- API Models ---
class ChatRequest(BaseModel):
    user_id: str = "default_user"
    query: str

class ChatResponse(BaseModel):
    reply: str
    ui_data: Dict[str, Any]
print("--- app/main.py: Pydantic Models DEFINED ---")

# --- In-Memory History Store ---
conversation_histories: Dict[str, List[Dict[str, str]]] = {}
HISTORY_LIMIT = 10
print("--- app/main.py: Conversation History Store INITIALIZED ---")


# --- Serve Static HTML File for the Root Path ---
@app.get("/", response_class=FileResponse)
async def read_index():
    print("--- app/main.py: / endpoint CALLED ---")
    html_file_path = "app/static/htmlsim.html"
    try:
        if not os.path.exists(html_file_path):
            print(f"--- app/main.py: ERROR - {html_file_path} NOT FOUND for / endpoint ---")
        print(f"--- app/main.py: Attempting to serve {html_file_path} for / endpoint ---")
        return FileResponse(html_file_path)
    except Exception as e:
        print(f"--- app/main.py: ERROR in / endpoint: {e} ---")
        raise

@app.get("/health")
async def health_check():
    print("--- app/main.py: /health endpoint CALLED ---")
    return {"status": "ok_ai_service_import_test"}

# `/chat` endpoint is NOT added back yet. We first want to ensure the imports work.

print("--- app/main.py: BOTTOM OF FILE, APP DEFINED (Importing AI Service Test) ---")