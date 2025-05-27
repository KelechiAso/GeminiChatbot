# app/main.py
print("--- app/main.py: TOP OF FILE (HTML + CORS + Models Test) ---")

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware # Add this
from pydantic import BaseModel # Add this
from typing import List, Dict, Any, Optional # Add these for Pydantic models
import os

print("--- app/main.py: Basic imports DONE (HTML + CORS + Models Test) ---")

app = FastAPI(title="SPAI - HTML + CORS + Models Test")
print("--- app/main.py: FastAPI INSTANCE CREATED (HTML + CORS + Models Test) ---")

# --- CORS ---
origins = ["*",] # For demo purposes
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


# --- Serve Static HTML File for the Root Path ---
@app.get("/", response_class=FileResponse)
async def read_index():
    print("--- app/main.py: / endpoint CALLED (HTML + CORS + Models Test) ---")
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
    print("--- app/main.py: /health endpoint CALLED (HTML + CORS + Models Test) ---")
    return {"status": "ok_html_cors_models_test"}

print("--- app/main.py: BOTTOM OF FILE, APP DEFINED (HTML + CORS + Models Test) ---")