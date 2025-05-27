# app/main.py
print("--- app/main.py: TOP OF FILE (Full Chat Logic Test) ---")

from fastapi import FastAPI, HTTPException, Request
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
    # Define placeholders if import fails, so app can at least start for basic routes
    async def extract_sports_info(*args, **kwargs): return {"input_type": "error", "message": "AI service not loaded"}
    async def fetch_raw_text_data(*args, **kwargs): return "-- AI SERVICE NOT LOADED --"
    async def get_structured_data_and_reply_via_tools(*args, **kwargs): return {"reply": "AI service not loaded", "ui_data": {"component_type": "generic_text", "data": {}}}


app = FastAPI(title="SPAI - Full Chat Logic Test") # Updated title
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
        if not os.path.exists(html_file_path): # Basic check
            print(f"--- app/main.py: ERROR - {html_file_path} NOT FOUND for / endpoint ---")
            # Fallback or raise HTTPException for a proper 404 if file not found
            raise HTTPException(status_code=404, detail="Index HTML not found.")
        print(f"--- app/main.py: Attempting to serve {html_file_path} for / endpoint ---")
        return FileResponse(html_file_path)
    except Exception as e:
        print(f"--- app/main.py: ERROR in / endpoint: {e} ---")
        raise HTTPException(status_code=500, detail="Internal server error serving index.")


@app.get("/health")
async def health_check():
    print("--- app/main.py: /health endpoint CALLED ---")
    return {"status": "ok_full_chat_logic_test"}


# --- Main Chat Endpoint (Re-instated) ---
@app.post("/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    print(f"--- app/main.py: /chat endpoint CALLED by user: {request.user_id} ---")
    user_id = request.user_id
    user_query = request.query
    if not user_query:
        print("--- app/main.py: /chat - Query is empty ---")
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    final_reply = "Sorry, I encountered an issue processing your sports/gaming request."
    final_ui_data = {"component_type": "generic_text", "data": {"message": "No UI data to display."}}
    current_history = conversation_histories.get(user_id, [])
    parsed_info = None

    try:
        # --- Step 0: Extract Intent/Entities ---
        print(f"\n--- Step 0 (main.py): Extracting info for query: '{user_query[:50]}...' ---")
        parsed_info = await extract_sports_info(user_query, current_history)
        
        if not isinstance(parsed_info, dict) or parsed_info.get("input_type") == "error":
             error_msg = parsed_info.get('message', 'Query parsing failed')
             print(f"!!! Step 0 (main.py): Extraction failed or returned error: {error_msg}")
             # Return a valid ChatResponse for client-side handling
             return ChatResponse(reply=f"Error understanding request: {error_msg}", ui_data=final_ui_data)
        
        print(f"--- Step 0 (main.py) Result (parsed_info):")
        pprint.pprint(parsed_info) # Pretty print for better log readability

        input_type_from_step_0 = parsed_info.get("input_type")
        direct_reply_from_step_0 = parsed_info.get("conversation")
        short_circuit_types = ["acknowledgment", "simple_greeting", "invalid_request", "out_of_scope_request"]

        if input_type_from_step_0 in short_circuit_types and \
           direct_reply_from_step_0 and \
           isinstance(direct_reply_from_step_0, str) and \
           direct_reply_from_step_0.strip():
            print(f"--- Step 0 (main.py) identified as '{input_type_from_step_0}' with a direct reply. Short-circuiting. ---")
            final_reply = direct_reply_from_step_0
            if input_type_from_step_0 == "out_of_scope_request":
                final_ui_data = {"component_type": "generic_text", "data": {"message": "Query outside of defined scope."}}
            # final_ui_data remains default generic_text for other short-circuited replies
        else:
            # --- Full pipeline with Tool Calling for Step 2 ---
            print(f"--- Step 1 (main.py): Attempting to fetch raw text data (if applicable for input_type: {input_type_from_step_0}) ---")
            raw_text_data = await fetch_raw_text_data(user_query, parsed_info, current_history)
            print(f"--- Step 1 (main.py) Result (raw_text_data snippet): {raw_text_data[:100]}... ---")


            print(f"--- Step 2 (main.py): Generating reply and UI data via Tool Calling ---")
            final_data_dict = await get_structured_data_and_reply_via_tools(
                parsed_info,
                current_history,
                raw_text_data
            )

            # --- Step 3 (main.py): Processing final dict from Step 2 ---
            if not isinstance(final_data_dict, dict) or "reply" not in final_data_dict or "ui_data" not in final_data_dict:
                 print(f"!!! Step 3 (main.py) ERROR: Tool calling step did not return valid dict structure. Using fallback replies.")
                 # final_reply and final_ui_data will use their initial default error messages
            else:
                 final_reply = final_data_dict.get("reply", "Request processed.")
                 final_ui_data = final_data_dict.get("ui_data", {"component_type": "generic_text", "data": {"message": "UI data was expected but not fully generated."}})
                 print(f">>> Step 3 (main.py): Successfully received reply/ui_data. UI Component: {final_ui_data.get('component_type')}")
        
        if not final_reply or not final_reply.strip():
            if input_type_from_step_0 == "acknowledgment": final_reply = "Okay."
            else: final_reply = "Request processed. Ask me about sports or gaming!"


        # --- Step 4: Update History ---
        print(f"--- Step 4 (main.py): Updating History ---")
        current_history.append({"role": "user", "content": user_query})
        if final_reply and final_reply.strip(): 
             current_history.append({"role": "assistant", "content": final_reply})
             print(f">>> Assistant reply added to history: '{final_reply[:100]}...'")
        else:
            print(f">>> Skipping assistant reply in history update due to empty content.")
        
        conversation_histories[user_id] = current_history[-HISTORY_LIMIT:]
        print(f">>> History for {user_id} updated. Length: {len(conversation_histories[user_id])}")

        # --- Step 5: Assemble and Return ---
        final_response_object = ChatResponse(reply=final_reply, ui_data=final_ui_data)
        print("--- Request processing complete (main.py). ---")
        return final_response_object

    except HTTPException as http_exc: # Re-raise FastAPI's own HTTPExceptions
        print(f"!!! HTTP EXCEPTION CAUGHT directly in /chat: {http_exc.detail}")
        raise http_exc
    except Exception as e: # Catch any other unexpected errors
        error_type = type(e).__name__
        print(f"!!! UNHANDLED EXCEPTION in /chat endpoint (main.py) !!!")
        print(f"Exception Type: {error_type}")
        print(f"Exception details: {e}")
        traceback.print_exc() # Print full traceback to server logs
        # Return a generic 500 error in the expected ChatResponse format
        return ChatResponse(
             reply=f"Sorry, a critical internal server error occurred ({error_type}). Please try again later.",
             ui_data={"component_type": "generic_text", "data": {"error": f"A critical server error occurred: {error_type}"}}
        )

print("--- app/main.py: BOTTOM OF FILE, APP DEFINED (Full Chat Logic Test) ---")