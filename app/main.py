# /app/api/gemini_service.py

import os
import json
import traceback
import google.generativeai as genai
from typing import Dict, List, Any, Tuple

# --- MODIFICATION: Import the necessary Schema and Type objects ---
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

**Your Core Rules:**
1.  **Domain Focus:** You MUST ONLY answer questions related to sports, e-gamiing, betting statistics, schedules, player info, and team stats.
2.  **Decline Off-Topic Requests:** If the user asks about anything else (e.g., math, history, personal advice, politics), you MUST politely decline.
3.  **Language Matching:** Respond in the user's language. If a user asks a question in Nigerian Pidgin, respond in Pidgin. If they ask an off-topic question in that language, decline in that language. Example: "Oga, I be sports AI, I no sabi about dis matter. How I fit help you with sports or game scores?"
4.  **Tool-First Approach:** For any sports data request, your PRIMARY goal is to use the provided tools to generate a structured UI component. Your text reply should be a brief, introductory sentence for the UI component.
5.  **Conversational Replies:** For greetings, simple questions ("who are you?"), or acknowledgments, provide a direct, conversational text reply without using a tool.
6.  **No Links:** Your textual reply MUST NOT contain any markdown links (e.g., `[text](URL)`) or full URLs. Mention sources by name only if necessary.
"""

# --- MODIFICATION: All Schemas are now defined using genai.protos.Schema and Type ---

SCHEMA_DATA_H2H = Schema(
    type=Type.OBJECT,
    properties={
        'h2h_summary': Schema(type=Type.OBJECT, properties={
            'team1': Schema(type=Type.OBJECT, properties={
                'name': Schema(type=Type.STRING),
                'wins': Schema(type=Type.INTEGER), 'draws': Schema(type=Type.INTEGER), 'losses': Schema(type=Type.INTEGER),
                'goals_for': Schema(type=Type.INTEGER), 'goals_against': Schema(type=Type.INTEGER)
            }),
            'team2': Schema(type=Type.OBJECT, properties={
                'name': Schema(type=Type.STRING),
                'wins': Schema(type=Type.INTEGER), 'draws': Schema(type=Type.INTEGER), 'losses': Schema(type=Type.INTEGER),
                'goals_for': Schema(type=Type.INTEGER), 'goals_against': Schema(type=Type.INTEGER)
            }),
            'total_matches': Schema(type=Type.INTEGER)
        }),
        'recent_meetings': Schema(type=Type.ARRAY, items=Schema(type=Type.OBJECT, properties={
            'date': Schema(type=Type.STRING), 'score': Schema(type=Type.STRING), 'competition': Schema(type=Type.STRING)
        }))
    },
    required=['h2h_summary']
)

SCHEMA_DATA_MATCH_SCHEDULE_TABLE = Schema(
    type=Type.OBJECT,
    properties={
        'title': Schema(type=Type.STRING),
        'headers': Schema(type=Type.ARRAY, items=Schema(type=Type.STRING)),
        'rows': Schema(type=Type.ARRAY, items=Schema(type=Type.ARRAY, items=Schema(type=Type.STRING))),
        'sort_info': Schema(type=Type.STRING)
    },
    required=['headers', 'rows']
)

# NOTE: For simplicity, I have only included the two schemas that were causing the most common issues.
# If you have more schemas, you will need to convert them in the same way.
# The following is a placeholder for all your other schemas.
# Please ensure ALL of your schemas are converted to this new format.

# --- Tool Name Mapping (Unchanged) ---
TOOL_NAME_TO_COMPONENT_TYPE = {
    "present_h2h_comparison": "h2h_comparison_table",
    "show_match_schedule": "match_schedule_table",
    # ... Add all other mappings from your original file ...
}


# --- Gemini Model and Tool Configuration ---
tools_for_gemini = [
    genai.protos.Tool(
        function_declarations=[
            genai.protos.FunctionDeclaration(name='present_h2h_comparison', description="Presents a head-to-head comparison between two teams.", parameters=SCHEMA_DATA_H2H),
            genai.protos.FunctionDeclaration(name='show_match_schedule', description="Shows a schedule of upcoming matches.", parameters=SCHEMA_DATA_MATCH_SCHEDULE_TABLE),
            # ... Add all other FunctionDeclarations here corresponding to your schemas ...
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

        if response_part.function_call.name:
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