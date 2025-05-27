# /app/main.py

import json
import traceback
import pprint # Optional: For detailed dictionary printing during debugging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Tuple

# --- Imports for the 3-Step AI Flow ---
from api.openai_service import (
    extract_sports_info,
    fetch_raw_text_data,
    get_structured_data_and_reply_via_tools
)

# --- In-Memory History Store (Replace for Production) ---
conversation_histories: Dict[str, List[Dict[str, str]]] = {}
HISTORY_LIMIT = 8 # Slightly increased history limit for better context
                  # Consider making this configurable or even per-user dynamic

# --- API Models (Unchanged) ---
class ChatRequest(BaseModel):
    user_id: str = "default_user"
    query: str

class ChatResponse(BaseModel):
    reply: str
    ui_data: Dict[str, Any]

# --- FastAPI App & CORS (Unchanged) ---
app = FastAPI(
    title="Sports Chatbot Microservice (SPAI)",
    description="Provides sports stats and info. Backend sends structured UI data."
)

origins = ["*",]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Health Check Endpoint (Unchanged) ---
@app.get("/health")
def health_check():
    return {"status": "ok"}

# --- Main Chat Endpoint (Orchestrates AI steps) ---
@app.post("/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    user_id = request.user_id
    user_query = request.query
    if not user_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    final_reply = "Sorry, an unexpected internal error occurred."
    final_ui_data = {"component_type": "generic_text", "data": {}}
    current_history = conversation_histories.get(user_id, [])
    parsed_info = None

    try:
        # --- Step 0: Extract Intent/Entities (GPT-3.5, History-Aware, V3 Prompt) ---
        print(f"\n--- Step 0: Extracting info for query: '{user_query[:50]}...' ---")
        # Pass current_history to extract_sports_info
        parsed_info = await extract_sports_info(user_query, current_history)
        
        if not isinstance(parsed_info, dict) or parsed_info.get("input_type") == "error":
             error_msg = parsed_info.get('message', 'query parsing failed') if isinstance(parsed_info, dict) else 'query parsing failed'
             print(f"!!! Extraction failed or returned error: {error_msg}")
             return ChatResponse(reply=f"Error understanding request: {error_msg}", ui_data=final_ui_data)
        print(f"--- Step 0 Result (parsed_info): ")
        pprint.pprint(parsed_info) # Pretty print for better readability

        # --- OPTIONAL SHORT-CIRCUIT for "acknowledgment" type if Step 0 provided a direct reply ---
        input_type_from_step_0 = parsed_info.get("input_type")
        conversation_reply_from_step_0 = parsed_info.get("conversation")

        if input_type_from_step_0 == "acknowledgment" and \
           conversation_reply_from_step_0 and \
           conversation_reply_from_step_0 != user_query: # Ensure it's not just echoing the user
            print("--- Step 0 identified as 'acknowledgment' with a direct reply. Short-circuiting. ---")
            final_reply = conversation_reply_from_step_0
            final_ui_data = {"component_type": "generic_text", "data": {}}
            # Skip Step 1 and Step 2 for these simple cases
        else:
            # --- Step 1: Fetch Raw Text Data (Search Model) ---
            # This step will now be skipped internally by fetch_raw_text_data if input_type is not relevant
            print(f"--- Step 1: Attempting to fetch raw text data (if applicable for input_type: {input_type_from_step_0}) ---")
            raw_text_data = await fetch_raw_text_data(user_query, parsed_info, current_history)

            # --- Step 2: Generate Final Reply & Structured UI Data (GPT-4o JSON Mode, V2 Prompt) ---
            print(f"--- Step 2: Generating final reply and dynamic UI structure ---")
            final_data_dict = await get_structured_data_and_reply_via_tools(
                parsed_info,
                current_history,
                raw_text_data
            )

            # --- Step 3: Process Final Dictionary ---
            print(f"--- Step 3: Processing final dict ---")
            if not isinstance(final_data_dict, dict) or "reply" not in final_data_dict or "ui_data" not in final_data_dict:
                 print(f"!!! ERROR: Final generation step did not return valid dict structure. Using fallback.")
                 # final_reply and final_ui_data remain as default error
            else:
                 print(">>> Successfully received final reply/ui_data dict from processing step.")
                 final_reply = final_data_dict.get("reply", "Error: Reply missing from AI.")
                 final_ui_data = final_data_dict.get("ui_data", {"component_type": "generic_text", "data": {"error": "UI data missing"}})
                 print(f">>> Sending structured ui_data (type: {final_ui_data.get('component_type')}) to frontend.")


        # Ensure final_ui_data structure is always valid before returning
        if not isinstance(final_ui_data, dict): final_ui_data = {"component_type": "generic_text", "data": {}}
        if "component_type" not in final_ui_data: final_ui_data["component_type"] = "generic_text"
        if "data" not in final_ui_data: final_ui_data["data"] = {}
        if not final_reply: # Ensure reply is not empty, provide a minimal one if it is.
            if input_type_from_step_0 == "acknowledgment":
                final_reply = "Okay." # Minimal fallback if LLM somehow produced empty for acknowledgment
            else:
                final_reply = "I've processed that." # Generic fallback for other empty replies

        # --- Step 4: Update History ---
        print(f"--- Step 4: Updating History ---")
        # Add user message to history regardless of reply success, to track user's full conversation path.
        current_history.append({"role": "user", "content": user_query})

        # Add assistant reply to history only if it's a meaningful reply.
        # Avoid adding very short, purely mechanical acknowledgments if they don't add conversational value for the LLM.
        # However, for now, we'll add all non-error replies.
        # The LLM itself should learn to ignore simple "Okay." from assistant in history if not relevant.
        if isinstance(final_reply, str) and \
           "Sorry," not in final_reply and \
           "Error " not in final_reply and \
           final_reply: # Ensure reply is not empty
             current_history.append({"role": "assistant", "content": final_reply})
             print(f">>> Assistant reply added to history: '{final_reply[:100]}...'")
        else:
            print(f">>> Skipping assistant reply in history update due to error, missing, or empty reply. User query still added.")
            # If assistant reply was empty, remove the last user message too if we decide not to store one-sided entries.
            # For now, keeping user message.

        conversation_histories[user_id] = current_history[-HISTORY_LIMIT:]
        print(f">>> History for {user_id} updated. Length: {len(conversation_histories[user_id])}")


        # --- Step 5: Assemble and Return ---
        final_response_object = ChatResponse(
            reply=final_reply,
            ui_data=final_ui_data
        )
        print("--- Request processing complete ---")
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
             reply=f"Sorry, a critical internal error occurred ({error_type}). Please try again later.",
             ui_data={"component_type": "generic_text", "data": {"error": f"{error_type}"}}
        )

# ... (rest of the file, e.g., running instructions)