# app/main.py
print("--- app/main.py: TOP OF FILE (HTML + Globals Test) ---")

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json         # Add this if your original chat logic uses it directly
import traceback    # Add this for more detailed error logging later
import pprint       # Add this for debugging print statements later

print("--- app/main.py: Basic imports DONE (HTML + Globals Test) ---")

app = FastAPI(title="SPAI - HTML + Globals Test")
print("--- app/main.py: FastAPI INSTANCE CREATED (HTML + Globals Test) ---")

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
HISTORY_LIMIT = 10 # Or your preferred limit
print("--- app/main.py: Conversation History Store INITIALIZED ---")


# --- Serve Static HTML File for the Root Path ---
@app.get("/", response_class=FileResponse)
async def read_index():
    print("--- app/main.py: / endpoint CALLED (HTML + Globals Test) ---")
    html_file_path = "app/static/htmlsim.html"
    try:
        if not os.path.exists(html_file_path):
            print(f"--- app/main.py: ERROR - {html_file_path} NOT FOUND ---")
        print(f"--- app/main.py: Attempting to serve {html_file_path} ---")
        return FileResponse(html_file_path)
    except Exception as e:
        print(f"--- app/main.py: ERROR in / endpoint: {e} ---")
        raise

@app.get("/health")
async def health_check():
    print("--- app/main.py: /health endpoint CALLED (HTML + Globals Test) ---")
    return {"status": "ok_html_globals_test"}

print("--- app/main.py: BOTTOM OF FILE, APP DEFINED (HTML + Globals Test) ---")