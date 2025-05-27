# /app/main.py

import json
import traceback
import pprint
import os # Add os import for path joining
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # Import StaticFiles
from fastapi.responses import FileResponse # Import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# --- Imports for the AI Flow ---
from api.openai_service import ( # Assuming api is at the same level as main.py if run from project root
    extract_sports_info,
    fetch_raw_text_data,
    get_structured_data_and_reply_via_tools
)

# --- In-Memory History Store ---
conversation_histories: Dict[str, List[Dict[str, str]]] = {}
HISTORY_LIMIT = 10

# --- API Models ---
class ChatRequest(BaseModel):
    user_id: str = "default_user"
    query: str

class ChatResponse(BaseModel):
    reply: str
    ui_data: Dict[str, Any]

# --- FastAPI App ---
app = FastAPI(
    title="Sports Chatbot Microservice (SPAI) - Web UI",
    description="Provides sports and gaming info with a web interface."
)

# --- CORS ---
origins = ["*",] # Keep this for now, especially if API might be called from other places
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Serve Static HTML File for the Root Path ---
@app.get("/", response_class=FileResponse)
async def read_index():
    # Construct the path to htmlsim.html
    # This assumes 'static' directory is inside the 'app' directory,
    # and main.py is also in the 'app' directory.
    # If your execution context is the project root, the path needs to be relative to that.
    # For Railway, when uvicorn app.main:app is run from the project root,
    # the path needs to be 'app/static/htmlsim.html'
    html_file_path = os.path.join(os.path.dirname(__file__), "static", "htmlsim.html")
    # A more robust way if main.py is in 'app/' and 'static' is also in 'app/'
    # and uvicorn is run from the project root:
    # current_dir = os.path.dirname(os.path.abspath(__file__)) # Gets directory of main.py (app/)
    # html_file_path = os.path.join(current_dir, "static", "htmlsim.html")

    # However, if your uvicorn command `uvicorn app.main:app` is run from the project root,
    # and your static files are in `app/static`, this should work:
    return FileResponse("app/static/htmlsim.html")

# --- API Endpoints ---
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    user_id = request.user_id
    user_query = request.query
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    final_reply = "Sorry, I encountered an issue processing your sports/gaming request."
    final_ui_data = {"component_type": "generic_text", "data": {"message": "No UI data to display."}}
    current_history = conversation_histories.get(user_id, [])
    parsed_info = None

    try:
        # --- Step 0: Extract Intent/Entities ---
        print(f"\n--- Step 0: Extracting info for query: '{user_query[:50]}...' ---")
        parsed_info = await extract_sports_info(user_query, current_history)

        if not isinstance(parsed_info, dict) or parsed_info.get("input_type") == "error":
             error_msg = parsed_info.get('message', 'Query parsing failed')
             print(f"!!! Extraction failed or returned error: {error_msg}")
             return ChatResponse(reply=f"Error understanding request: {error_msg}", ui_data=final_ui_data)

        print(f"--- Step 0 Result (parsed_info):")
        pprint.pprint(parsed_info)

        input_type_from_step_0 = parsed_info.get("input_type")
        direct_reply_from_step_0 = parsed_info.get("conversation")
        short_circuit_types = ["acknowledgment", "simple_greeting", "invalid_request", "out_of_scope_request"]

        if input_type_from_step_0 in short_circuit_types and \
           direct_reply_from_step_0 and \
           isinstance(direct_reply_from_step_0, str) and \
           direct_reply_from_step_0.strip():
            print(f"--- Step 0 identified as '{input_type_from_step_0}' with a direct reply. Short-circuiting. ---")
            final_reply = direct_reply_from_step_0
            if input_type_from_step_0 == "out_of_scope_request":
                final_ui_data = {"component_type": "generic_text", "data": {"message": "Query outside of defined scope."}}
        else:
            print(f"--- Step 1: Attempting to fetch raw text data (if applicable for input_type: {input_type_from_step_0}) ---")
            raw_text_data = await fetch_raw_text_data(user_query, parsed_info, current_history)

            print(f"--- Step 2: Generating reply and UI data via Tool Calling ---")
            final_data_dict = await get_structured_data_and_reply_via_tools(
                parsed_info,
                current_history,
                raw_text_data
            )

            if not isinstance(final_data_dict, dict) or "reply" not in final_data_dict or "ui_data" not in final_data_dict:
                 print(f"!!! ERROR: Tool calling step did not return valid dict structure. Using fallback replies.")
            else:
                 final_reply = final_data_dict.get("reply", "Request processed.")
                 final_ui_data = final_data_dict.get("ui_data", {"component_type": "generic_text", "data": {"message": "UI data was expected but not fully generated."}})
                 print(f">>> Successfully received reply/ui_data from Step 2. UI Component: {final_ui_data.get('component_type')}")

        if not final_reply or not final_reply.strip():
            if input_type_from_step_0 == "acknowledgment": final_reply = "Okay."
            else: final_reply = "Request processed. Ask me about sports or gaming!"

        print(f"--- Step 4: Updating History ---")
        current_history.append({"role": "user", "content": user_query})
        if final_reply and final_reply.strip():
             current_history.append({"role": "assistant", "content": final_reply})
             print(f">>> Assistant reply added to history: '{final_reply[:100]}...'")
        else:
            print(f">>> Skipping assistant reply in history update due to empty content.")

        conversation_histories[user_id] = current_history[-HISTORY_LIMIT:]
        print(f">>> History for {user_id} updated. Length: {len(conversation_histories[user_id])}")

        final_response_object = ChatResponse(reply=final_reply, ui_data=final_ui_data)
        print("--- Request processing complete. ---")
        return final_response_object

    except HTTPException as http_exc:
        print(f"!!! HTTP EXCEPTION CAUGHT in main.py handle_chat: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        error_type = type(e).__name__
        print(f"!!! UNHANDLED EXCEPTION in main.py handle_chat !!!")
        print(f"Exception Type: {error_type}")
        print(f"Exception details: {e}")
        traceback.print_exc()
        return ChatResponse(
             reply=f"Sorry, a critical internal error occurred ({error_type}). Please try again later or contact support.",
             ui_data={"component_type": "generic_text", "data": {"error": f"A critical server error occurred: {error_type}"}}
        )

# Optional: Mount a static directory if you have CSS/JS files later
# app.mount("/static_assets", StaticFiles(directory="app/static_assets"), name="static_assets")