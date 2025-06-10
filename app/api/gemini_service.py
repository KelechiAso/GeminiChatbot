# /app/api/gemini_service.py

import os
import json
import traceback
import google.generativeai as genai
from typing import Dict, List, Any, Tuple

# --- MODIFICATION: Import both Schema and Type ---
from google.generativeai.protos import Schema, Type

# --- Setup ---
print("--- gemini_service.py: TOP OF FILE ---")
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable not set.")
    
    genai.configure(api_key=api_key)
    print("--- gemini_service.py: Google AI SDK Configured ---")

except Exception as e:
    print(f"--- gemini_service.py: !!! FAILED to configure Google AI SDK: {e} !!! ---")
    traceback.print_exc()
    raise e

# --- System Prompt (Unchanged) ---
SYSTEM_PROMPT = """
You are GameNerd, a specialized AI assistant for sports and gaming information ONLY.
Your personality is helpful, concise, and friendly.
Your goal is to use the provided tools to generate structured UI components for sports data requests.
"""

# --- MODIFICATION: Schemas are now correctly defined using Schema(type_=...) ---
# The keyword is `type_` with a trailing underscore, not `type`.

SCHEMA_DATA_H2H = Schema(
    type_=Type.OBJECT,
    properties={
        'h2h_summary': Schema(type_=Type.OBJECT, properties={
            'team1': Schema(type_=Type.OBJECT, properties={
                'name': Schema(type_=Type.STRING),
                'wins': Schema(type_=Type.INTEGER), 'draws': Schema(type_=Type.INTEGER), 'losses': Schema(type_=Type.INTEGER),
                'goals_for': Schema(type_=Type.INTEGER), 'goals_against': Schema(type_=Type.INTEGER)
            }),
            'team2': Schema(type_=Type.OBJECT, properties={
                'name': Schema(type_=Type.STRING),
                'wins': Schema(type_=Type.INTEGER), 'draws': Schema(type_=Type.INTEGER), 'losses': Schema(type_=Type.INTEGER),
                'goals_for': Schema(type_=Type.INTEGER), 'goals_against': Schema(type_=Type.INTEGER)
            }),
            'total_matches': Schema(type_=Type.INTEGER)
        }),
        'recent_meetings': Schema(type_=Type.ARRAY, items=Schema(type_=Type.OBJECT, properties={
            'date': Schema(type_=Type.STRING), 'score': Schema(type_=Type.STRING), 'competition': Schema(type_=Type.STRING)
        }))
    },
    required=['h2h_summary']
)

SCHEMA_DATA_MATCH_SCHEDULE_TABLE = Schema(
    type_=Type.OBJECT,
    properties={
        'title': Schema(type_=Type.STRING),
        'headers': Schema(type_=Type.ARRAY, items=Schema(type_=Type.STRING)),
        'rows': Schema(type_=Type.ARRAY, items=Schema(type_=Type.ARRAY, items=Schema(type_=Type.STRING))),
        'sort_info': Schema(type_=Type.STRING)
    },
    required=['headers', 'rows']
)

# --- Tool Name Mapping (Unchanged) ---
TOOL_NAME_TO_COMPONENT_TYPE = {
    "present_h2h_comparison": "h2h_comparison_table",
    "show_match_schedule": "match_schedule_table",
}

# --- Gemini Model and Tool Configuration (Unchanged) ---
tools_for_gemini = [
    genai.protos.Tool(
        function_declarations=[
            genai.protos.FunctionDeclaration(name='present_h2h_comparison', description="Presents a head-to-head comparison between two teams.", parameters=SCHEMA_DATA_H2H),
            genai.protos.FunctionDeclaration(name='show_match_schedule', description="Shows a schedule of upcoming matches.", parameters=SCHEMA_DATA_MATCH_SCHEDULE_TABLE),
        ]
    )
]

model = genai.GenerativeModel(
    model_name='gemini-1.5-flash-latest',
    system_instruction=SYSTEM_PROMPT,
    tools=tools_for_gemini
)
print("--- gemini_service.py: Gemini Model INITIALIZED (gemini-1.5-flash-latest) ---")


# --- Main Service Function (Unchanged) ---
async def generate_gemini_response(
    user_query: str,
    conversation_history: List[Dict[str, str]]
) -> Tuple[str, Dict[str, Any]]:
    print(f"--- gemini_service.py: Generating response for query: '{user_query[:50]}...' ---")
    
    final_reply = "Sorry, I couldn't process that. Please try again."
    final_ui_data = {"component_type": "generic_text", "data": {}}

    try:
        history_for_model = []
        for turn in conversation_history:
            role = 'user' if turn.get('role') == 'user' else 'model'
            history_for_model.append({'role': role, 'parts': [{'text': turn.get('content', '')}]})

        chat = model.start_chat(history=history_for_model)
        
        print(">>> Sending message to Gemini...")
        response = await chat.send_message_async(user_query)
        
        if not response.candidates:
             return "I'm sorry, I couldn't generate a response for that. Please try again.", final_ui_data

        response_part = response.candidates[0].content.parts[0]

        if hasattr(response_part, 'function_call') and response_part.function_call.name:
            tool_name = response_part.function_call.name
            tool_args = response_part.function_call.args
            
            print(f">>> Gemini wants to call TOOL: '{tool_name}'")
            
            component_type = TOOL_NAME_TO_COMPONENT_TYPE.get(tool_name, "generic_text")
            data_dict = {key: val for key, val in tool_args.items()}

            final_ui_data = {
                "component_type": component_type,
                "data": data_dict
            }
            
            component_name_readable = component_type.replace('_', ' ').title()
            final_reply = f"Of course, here is the {component_name_readable} you asked for."
            
            if response.text and response.text.strip():
                final_reply = response.text

        elif response.text:
            print(">>> Gemini provided a direct text reply.")
            final_reply = response.text
            final_ui_data = {"component_type": "generic_text", "data": {"message": "Conversational reply."}}
        
        print(f"--- Gemini response generated successfully. Reply: '{final_reply[:100]}...'")
        return final_reply, final_ui_data

    except Exception as e:
        print(f"!!! An error occurred in generate_gemini_response: {e}")
        traceback.print_exc()
        error_reply = f"An unexpected error occurred while contacting the AI service: {type(e).__name__}."
        error_ui_data = {"component_type": "generic_text", "data": {"error": str(e)}}
        return error_reply, error_ui_data

print("--- gemini_service.py: BOTTOM OF FILE ---")