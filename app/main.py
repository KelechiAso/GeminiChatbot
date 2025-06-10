# /app/main.py

print("--- app/main.py: TOP OF FILE ---")
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, AsyncGenerator
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import traceback
import pprint

print("--- app/main.py: Standard imports DONE ---")

# This try/except block now works because gemini_service.py is fixed.
try:
    print("--- app/main.py: Attempting to import from api.gemini_service ---")
    from .api.gemini_service import generate_gemini_response
    print("--- app/main.py: SUCCESSFULLY IMPORTED from api.gemini_service ---")
except ImportError as e:
    print(f"--- app/main.py: !!! FAILED to import from api.gemini_service due to ImportError: {e} !!! ---")
    traceback.print_exc()
    raise e
except Exception as e:
    print(f"--- app/main.py: !!! FAILED to import from api.gemini_service due to OTHER error: {e} !!! ---")
    traceback.print_exc()
    raise e


app = FastAPI(
    title="Sports Chatbot Microservice (SPAI) - v3.0 (Gemini)",
    description="Provides fast, context-aware sports and gaming info using Google Gemini."
)
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
HISTORY_LIMIT = 12
print("--- app/main.py: Conversation History Store INITIALIZED ---")

# --- Static File and Health Check Endpoints ---
@app.get("/", response_class=FileResponse)
async def read_index():
    print("--- app/main.py: / endpoint CALLED ---")
    html_file_path = "app/static/htmlsim.html"
    if not os.path.exists(html_file_path):
        raise HTTPException(status_code=404, detail="Index HTML not found.")
    return FileResponse(html_file_path)

@app.get("/health")
async def health_check():
    print("--- app/main.py: /health endpoint CALLED ---")
    return {"status": "ok_v3.0_gemini"}

# --- Main Chat Endpoint ---
@app.post("/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    print(f"--- app/main.py: /chat CALLED by user: {request.user_id} with query: '{request.query[:50]}...' ---")
    user_id = request.user_id
    user_query = request.query

    if not user_query:
        print("--- app/main.py: /chat - Query is empty ---")
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    current_history = conversation_histories.get(user_id, [])

    try:
        print(f"--- Calling Gemini Service for user '{user_id}' ---")
        final_reply, final_ui_data = await generate_gemini_response(user_query, current_history)
        print(f"--- Gemini Service returned. UI Component: {final_ui_data.get('component_type')} ---")

        # Update conversation history
        current_history.append({"role": "user", "content": user_query})
        if final_reply and final_reply.strip():
            current_history.append({"role": "assistant", "content": final_reply})
        conversation_histories[user_id] = current_history[-HISTORY_LIMIT:]
        print(f">>> History for {user_id} updated. New length: {len(conversation_histories[user_id])}")

        # Return the final response
        return ChatResponse(reply=final_reply, ui_data=final_ui_data)

    except Exception as e:
        error_type = type(e).__name__
        print(f"!!! UNHANDLED EXCEPTION in /chat endpoint (main.py) !!!")
        print(f"Exception Type: {error_type}")
        print(f"Exception details: {str(e)}")
        traceback.print_exc()
        # Return a structured error response
        error_reply = f"Sorry, a critical server error occurred ({error_type}). Please try a different sports/gaming query."
        error_ui_data = {"component_type": "generic_text", "data": {"error": f"Server error: {error_type}"}}
        return ChatResponse(reply=error_reply, ui_data=error_ui_data)

print("--- app/main.py: BOTTOM OF FILE, APP DEFINED ---")