# /app/api/gemini_service.py

import os
import json
import traceback
import google.generativeai as genai
from typing import Dict, List, Any, Tuple

# --- Setup ---
print("--- gemini_service.py: TOP OF FILE ---")
try:
    # --- IMPORTANT ---
    # Make sure you have your Google API Key set as an environment variable.
    # For example: export GOOGLE_API_KEY="your_key_here"
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable not set.")
    
    genai.configure(api_key=api_key)
    print("--- gemini_service.py: Google AI SDK Configured ---")

except Exception as e:
    print(f"--- gemini_service.py: !!! FAILED to configure Google AI SDK: {e} !!! ---")
    traceback.print_exc()
    raise e

# --- System Prompt: The AI's Core Instructions ---
# This single prompt replaces the multiple, complex prompts from the old version.
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

# --- Tool Schemas (Adapted from your originals for Gemini) ---
# Keeping the function names and structures the same ensures the frontend doesn't break.
# Note: In Gemini, these are defined directly as part of the tool configuration.

# (The schemas like SCHEMA_DATA_H2H, SCHEMA_DATA_STANDINGS_TABLE, etc. are identical to your
# openai_service.py file. For brevity, they are not repeated here. You would copy/paste
# all the `SCHEMA_DATA_...` dictionaries into this file.)

# --- Paste all SCHEMA_DATA_... dictionaries here ---
SCHEMA_DATA_H2H = {
    "type": "object", "title": "H2HData", "description": "Data for head-to-head comparisons.",
    "properties": {
        "h2h_summary": {"type": "object", "properties": {
                "team1": {"type": "object", "properties": {"name": {"type": "string"}, "wins": {"type": ["integer", "null"]}, "draws": {"type": ["integer", "null"]}, "losses": {"type": ["integer", "null"]}, "goals_for": {"type": ["integer", "null"]}, "goals_against": {"type": ["integer", "null"]}}, "required": ["name"]},
                "team2": {"type": "object", "properties": {"name": {"type": "string"}, "wins": {"type": ["integer", "null"]}, "draws": {"type": ["integer", "null"]}, "losses": {"type": ["integer", "null"]}, "goals_for": {"type": ["integer", "null"]}, "goals_against": {"type": ["integer", "null"]}}, "required": ["name"]},
                "total_matches": {"type": ["integer", "null"]}}, "required": ["team1", "team2"]},
        "recent_meetings": {"type": "array", "items": {"type": "object", "properties": {"date": {"type": "string", "format": "date"}, "score": {"type": "string"}, "competition": {"type": "string"}}, "required": ["date", "score"]}}},
    "required": ["h2h_summary"]
}
SCHEMA_DATA_RESULTS_LIST = {
    "type": "object", "title": "ResultsListData", "description": "Data for a list of match results.",
    "properties": {"matches": {"type": "array", "items": {"type": "object", "properties": {
                    "date": {"type": "string"}, "time": {"type": "string"}, "competition": {"type": "string"}, "round": {"type": ["string", "null"]},
                    "home_team_name": {"type": "string"}, "away_team_name": {"type": "string"},
                    "score": {"type": "object", "properties": {"fulltime": {"type": "object", "properties": {"home": {"type": ["integer", "null"]}, "away": {"type": ["integer", "null"]}}}, "halftime": {"type": "object", "properties": {"home": {"type": ["integer", "null"]}, "away": {"type": ["integer", "null"]}}, "description": "Optional halftime score"}}, "required": ["fulltime"]},
                    "status": {"type": "string"}}, "required": ["date", "home_team_name", "away_team_name", "score", "status"]}}},
    "required": ["matches"]
}
SCHEMA_DATA_MATCH_SCHEDULE_TABLE = {
    "type": "object", "title": "MatchScheduleTableData", "description": "Data for a table of upcoming matches.",
    "properties": {"title": {"type": "string"}, "headers": {"type": "array", "items": {"type": "string"}},
                   "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                   "sort_info": {"type": ["string", "null"]}},
    "required": ["headers", "rows"]
}
# ... and so on for all your other schemas ...


# This maps the tool's function name to the component type the frontend expects.
TOOL_NAME_TO_COMPONENT_TYPE = {
    "present_h2h_comparison": "h2h_comparison_table",
    "display_standings_table": "standings_table",
    "show_match_schedule": "match_schedule_table",
    # ... Add all other mappings from your openai_service.py ...
}

# --- Gemini Model and Tool Configuration ---
# Define all the functions the model can call.
tools_for_gemini = [
    genai.protos.Tool(
        function_declarations=[
            genai.protos.FunctionDeclaration(name='present_h2h_comparison', description="Presents a head-to-head comparison between two teams.", parameters=SCHEMA_DATA_H2H),
            genai.protos.FunctionDeclaration(name='display_standings_table', description="Displays a league standings table.", parameters=SCHEMA_DATA_STANDINGS_TABLE),
            genai.protos.FunctionDeclaration(name='show_match_schedule', description="Shows a schedule of upcoming matches.", parameters=SCHEMA_DATA_MATCH_SCHEDULE_TABLE),
            genai.protos.FunctionDeclaration(name='list_match_results', description="Lists recent match results.", parameters=SCHEMA_DATA_RESULTS_LIST),
            # ... Add all other FunctionDeclarations here corresponding to your schemas ...
        ]
    )
]

# Using Gemini 1.5 Flash - it's very fast and capable, ideal for chat applications.
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash-latest',
    system_instruction=SYSTEM_PROMPT,
    tools=tools_for_gemini
)
print("--- gemini_service.py: Gemini Model INITIALIZED (gemini-1.5-flash-latest) ---")


# --- Main Service Function ---
async def generate_gemini_response(
    user_query: str,
    conversation_history: List[Dict[str, str]]
) -> Tuple[str, Dict[str, Any]]:
    """
    Generates a response from Gemini, handling tool calls and conversation history.
    Returns a tuple of (final_reply, final_ui_data).
    """
    print(f"--- gemini_service.py: Generating response for query: '{user_query[:50]}...' ---")
    
    # Defaults
    final_reply = "Sorry, I couldn't process that. Please try again."
    final_ui_data = {"component_type": "generic_text", "data": {}}

    try:
        # Build the history for the model
        history_for_model = []
        for turn in conversation_history:
            role = 'user' if turn.get('role') == 'user' else 'model'
            history_for_model.append({'role': role, 'parts': [{'text': turn.get('content', '')}]})

        # Start a chat session with the history
        chat = model.start_chat(history=history_for_model)
        
        # Send the user's new message
        print(">>> Sending message to Gemini...")
        response = await chat.send_message_async(user_query)
        response_part = response.candidates[0].content.parts[0]

        if response_part.function_call.name:
            # --- The model wants to call a tool ---
            tool_name = response_part.function_call.name
            tool_args = response_part.function_call.args
            
            print(f">>> Gemini wants to call TOOL: '{tool_name}'")
            
            # For this refactor, we assume the model has all info and doesn't need a real tool run.
            # It just structures the data. In a more advanced case, you could run code here
            # (e.g., a real API call to a sports data provider).

            # The model's job was to create the arguments for the tool (which is our UI data).
            component_type = TOOL_NAME_TO_COMPONENT_TYPE.get(tool_name, "generic_text")
            
            # Convert Gemini's args to a Python dict
            data_dict = {key: val for key, val in tool_args.items()}

            final_ui_data = {
                "component_type": component_type,
                "data": data_dict
            }
            
            # Generate a simple, introductory text reply
            component_name_readable = component_type.replace('_', ' ').title()
            final_reply = f"Of course, here is the {component_name_readable} you asked for."
            
            # Check if the model also sent a text reply alongside the tool call
            if response.text and response.text.strip():
                final_reply = response.text

        elif response.text:
            # --- The model provided a direct text answer ---
            print(">>> Gemini provided a direct text reply.")
            final_reply = response.text
            final_ui_data = {"component_type": "generic_text", "data": {"message": "Conversational reply."}}
        
        print(f"--- Gemini response generated successfully. Reply: '{final_reply[:100]}...'")
        return final_reply, final_ui_data

    except Exception as e:
        print(f"!!! An error occurred in generate_gemini_response: {e}")
        traceback.print_exc()
        # Return a safe error response
        error_reply = f"An unexpected error occurred while contacting the AI service: {type(e).__name__}."
        error_ui_data = {"component_type": "generic_text", "data": {"error": str(e)}}
        return error_reply, error_ui_data

print("--- gemini_service.py: BOTTOM OF FILE ---")