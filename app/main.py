# /app/main.py
print("--- app/main.py: TOP OF FILE ---")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse # Added StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncGenerator # Added AsyncGenerator
import os
import json
import traceback
import pprint

print("--- app/main.py: Standard imports DONE ---")

try:
    print("--- app/main.py: Attempting to import from .api.openai_service ---")
    from .api.openai_service import (
        extract_sports_info,
        fetch_raw_text_data,
        get_structured_data_and_reply_via_tools
    )
    print("--- app/main.py: SUCCESSFULLY IMPORTED from .api.openai_service ---")
except ImportError as e:
    print(f"--- app/main.py: !!! FAILED to import from .api.openai_service due to ImportError: {e} !!! ---")
    traceback.print_exc() 
    raise e 
except Exception as e: 
    print(f"--- app/main.py: !!! FAILED to import from .api.openai_service due to OTHER error: {e} !!! ---")
    traceback.print_exc()
    raise e 


app = FastAPI(
    title="Sports Chatbot Microservice (SPAI) - v2.2 SSE",
    description="Provides sports and gaming info using OpenAI tools, domain enforcement, and SSE."
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

# ChatResponse model is not used directly by the /chat endpoint anymore if it's always streaming
# class ChatResponse(BaseModel):
# reply: str
# ui_data: Dict[str, Any]
print("--- app/main.py: Pydantic Models DEFINED (ChatResponse might not be used for /chat endpoint) ---")

# --- In-Memory History Store ---
conversation_histories: Dict[str, List[Dict[str, str]]] = {}
HISTORY_LIMIT = 10
print("--- app/main.py: Conversation History Store INITIALIZED ---")


# --- SSE Generator Function ---
async def sse_text_and_ui_generator(
    text_reply_chunks: List[str], # Can be a list containing one full reply, or multiple chunks
    ui_data_obj: Dict[str, Any],
    is_error_reply: bool = False # Optional flag for client styling
) -> AsyncGenerator[str, None]:
    print(f"--- sse_generator: Starting. Text chunks count: {len(text_reply_chunks)}, UI data: {str(ui_data_obj)[:100]}...")
    for text_chunk in text_reply_chunks:
        if text_chunk: # Ensure chunk is not empty or None
            event_data = {"type": "text_chunk", "content": text_chunk}
            if is_error_reply: # Add error flag if it's an error message
                event_data["is_error"] = True
            yield f"data: {json.dumps(event_data)}\n\n"
            await asyncio.sleep(0.01) # Small delay to simulate streaming if it's one big chunk

    if ui_data_obj: # Ensure ui_data_obj is not None
        yield f"data: {json.dumps({'type': 'ui_data', 'content': ui_data_obj})}\n\n"
        await asyncio.sleep(0.01)

    yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
    print("--- sse_generator: Finished. ---")


# --- Serve Static HTML File for the Root Path ---
@app.get("/", response_class=FileResponse)
async def read_index():
    print("--- app/main.py: / endpoint CALLED ---")
    html_file_path = "app/static/htmlsim.html"
    try:
        if not os.path.exists(html_file_path):
            print(f"--- app/main.py: ERROR - {html_file_path} NOT FOUND for / endpoint ---")
            raise HTTPException(status_code=404, detail="Index HTML not found. Ensure app/static/htmlsim.html exists.")
        print(f"--- app/main.py: Attempting to serve {html_file_path} for / endpoint ---")
        return FileResponse(html_file_path)
    except Exception as e:
        print(f"--- app/main.py: ERROR in / endpoint: {e} ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error serving index: {str(e)}")

@app.get("/health")
async def health_check():
    print("--- app/main.py: /health endpoint CALLED ---")
    return {"status": "ok_v2.2_sse"}

# --- Main Chat Endpoint ---
# Removed response_model=ChatResponse as we are using StreamingResponse
@app.post("/chat") 
async def handle_chat(request: ChatRequest):
    print(f"--- app/main.py: /chat endpoint CALLED by user: {request.user_id} with query: '{request.query[:30]}...' ---")
    user_id = request.user_id
    user_query = request.query

    if not user_query:
        print("--- app/main.py: /chat - Query is empty ---")
        # For HTTPExceptions, we can't easily stream an SSE error, so return JSON error
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    final_reply_text = "Sorry, I'm having trouble processing sports/gaming requests right now."
    final_ui_data_obj = {"component_type": "generic_text", "data": {"message": "Default error UI."}}
    is_error_response = False
    current_history = conversation_histories.get(user_id, [])
    
    try:
        print(f"--- Step 0 (main.py): Extracting info for query: '{user_query[:50]}...' ---")
        parsed_info = await extract_sports_info(user_query, current_history)
        
        if not isinstance(parsed_info, dict) or parsed_info.get("input_type") == "error":
             error_msg = parsed_info.get('message', 'Query parsing failed at Step 0.')
             print(f"!!! Step 0 (main.py): Extraction failed or returned error: {error_msg}")
             final_reply_text = f"Error understanding your request: {error_msg}"
             is_error_response = True
             # Proceed to SSE generator to send this error
        else:
            print(f"--- Step 0 (main.py) Result (parsed_info):")
            pprint.pprint(parsed_info)

            input_type_from_step_0 = parsed_info.get("input_type")
            direct_reply_from_step_0 = parsed_info.get("conversation")
            short_circuit_types = ["acknowledgment", "simple_greeting", "invalid_request", "out_of_scope_request"]

            if input_type_from_step_0 in short_circuit_types and \
               direct_reply_from_step_0 and \
               isinstance(direct_reply_from_step_0, str) and \
               direct_reply_from_step_0.strip():
                print(f"--- Step 0 (main.py) identified as '{input_type_from_step_0}'. Short-circuiting with direct reply. ---")
                final_reply_text = direct_reply_from_step_0
                if input_type_from_step_0 == "out_of_scope_request":
                    final_ui_data_obj = {"component_type": "generic_text", "data": {"message": "This query is outside of my sports/gaming expertise."}}
                else: 
                    final_ui_data_obj = {"component_type": "generic_text", "data": {}}
            else:
                print(f"--- Step 1 (main.py): Attempting to fetch raw text data for input_type: {input_type_from_step_0} ---")
                raw_text_data = await fetch_raw_text_data(user_query, parsed_info, current_history)
                print(f"--- Step 1 (main.py) Result (raw_text_data snippet): {str(raw_text_data)[:150]}... ---")

                print(f"--- Step 2 (main.py): Generating reply and UI data via Tool Calling ---")
                final_data_dict = await get_structured_data_and_reply_via_tools(
                    parsed_info,
                    current_history,
                    raw_text_data
                )

                if not isinstance(final_data_dict, dict) or "reply" not in final_data_dict or "ui_data" not in final_data_dict:
                     print(f"!!! Step 3 (main.py) ERROR: Tool calling step (Step 2) returned invalid dict structure. Response: {str(final_data_dict)[:200]}")
                     final_reply_text = "There was an issue getting the details for your sports/gaming request."
                     is_error_response = True
                else:
                     final_reply_text = final_data_dict.get("reply", "Processed your sports/gaming request.")
                     final_ui_data_obj = final_data_dict.get("ui_data", {"component_type": "generic_text", "data": {"message": "No specific UI data was generated."}})
                     print(f">>> Step 3 (main.py): Successfully received reply/ui_data. UI Component: {final_ui_data_obj.get('component_type')}")
            
            if not final_reply_text or not final_reply_text.strip(): # Ensure there's always some reply
                if input_type_from_step_0 == "acknowledgment": final_reply_text = "Noted."
                else: final_reply_text = "Your sports/gaming query has been processed."
        
        # --- Update History ---
        print(f"--- Step 4 (main.py): Updating History ---")
        current_history.append({"role": "user", "content": user_query})
        if final_reply_text and final_reply_text.strip(): 
             current_history.append({"role": "assistant", "content": final_reply_text})
             print(f">>> Assistant reply added to history: '{final_reply_text[:100]}...'")
        else:
            print(f">>> Skipping assistant reply in history update due to empty content.")
        
        conversation_histories[user_id] = current_history[-HISTORY_LIMIT:]
        print(f">>> History for {user_id} updated. Length: {len(conversation_histories[user_id])}")

        print(f"--- Request processing complete (main.py). Preparing SSE response. Reply: '{final_reply_text[:50]}...' ---")
        return StreamingResponse(
            sse_text_and_ui_generator([final_reply_text], final_ui_data_obj, is_error_response),
            media_type="text/event-stream"
        )

    except HTTPException as http_exc: # This will be caught by FastAPI and returned as JSON
        print(f"!!! HTTP EXCEPTION CAUGHT directly in /chat: {http_exc.detail}")
        traceback.print_exc()
        raise http_exc 
    except Exception as e: # Catch any other unexpected errors
        error_type = type(e).__name__
        print(f"!!! UNHANDLED EXCEPTION in /chat endpoint (main.py) !!!")
        print(f"Exception Type: {error_type}")
        print(f"Exception details: {str(e)}")
        traceback.print_exc()
        
        # For unhandled exceptions, we also send an SSE stream with the error message
        error_reply_text = f"Sorry, a critical internal server error occurred ({error_type}). Please try a different sports/gaming query."
        error_ui_data_obj = {"component_type": "generic_text", "data": {"error": f"Server error: {error_type}"}}
        
        # Update history with the error if appropriate (or maybe not, to avoid polluting with server errors)
        # For now, we won't add this specific server crash error to history.

        return StreamingResponse(
            sse_text_and_ui_generator([error_reply_text], error_ui_data_obj, True), # Mark as error
            media_type="text/event-stream"
        )

print("--- app/main.py: BOTTOM OF FILE, APP DEFINED ---")