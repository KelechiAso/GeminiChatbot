# /app/api/openai_service.py

import json
import openai
import os
import asyncio
import traceback
import html
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional

from openai import AsyncOpenAI, Timeout # Ensure Timeout is imported

# --- Setup ---
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("CRITICAL ERROR: OPENAI_API_KEY environment variable not set.")

client = AsyncOpenAI(
    api_key=openai_api_key,
    timeout=Timeout(120.0, connect=10.0)
)

# --- Constants ---

# System prompt for Step 0: V3.2 - Added Out-of-Scope Request handling
SYSTEM_PROMPT_EXTRACTOR_V3_2 = """
Task: Analyze the **current user query** in the context of the **provided conversation history**. Extract structured sports information, classify the query, or provide a direct simple reply for acknowledgments/basic conversational turns/out-of-scope requests.

**Input Context:**
You will receive:
1.  (Optional) Recent `Conversation History`.
2.  The `Current User Query`.

**Instructions:**

1.  **Deeply Understand Context & History:**
    * Analyze `Conversation History` to understand the dialogue flow.
    * Determine if the `Current User Query` is an acknowledgment, a simple greeting, related to sports/gaming, or clearly off-topic.
    * Resolve pronouns, fill in missing entities, and understand implicit references.

2.  **Output JSON:** Based on your contextual understanding, output ONLY a **JSON** object:

    * **If the query is clearly unrelated to sports, gaming, betting statistics, or your capabilities as a sports AI (e.g., asking for math help, general knowledge unrelated to sports, personal advice, medical questions)**:
        * "input_type": "out_of_scope_request"
        * "conversation": "I am SPAI, an AI assistant focused on sports and gaming information. I can provide insights on scores, statistics, H2H details, and related topics. I'm unable to assist with requests outside of this domain, such as help with math assignments."
        * "original_query": The original current user input text.
        * "contextual_query_interpretation": "User query is outside of the AI's defined scope (sports and gaming)."

    * **If the query is a simple acknowledgment (e.g., "okay", "thanks", "got it", "nice")**:
        * "input_type": "acknowledgment"
        * "conversation": A brief, contextually appropriate affirmation (e.g., "You're welcome!", "Glad I could help!", "Okay.", or an empty string if no verbal reply seems natural). THIS IS INTENDED AS A DIRECT REPLY.
        * "original_query": The original current user input text.
        * "contextual_query_interpretation": "User is acknowledging previous information."

    * **If the query is a simple greeting (e.g., "hi", "hello") AND the conversation is just starting or history shows no active complex topic**:
        * "input_type": "simple_greeting"
        * "conversation": "Hello! I'm SPAI, your sports and gaming information assistant. How can I help you today?"
        * "original_query": The original current user input text.
        * "contextual_query_interpretation": "Simple user greeting."

    * **If the query asks about your identity/purpose (e.g., "who are you?") AND you haven't *just* introduced yourself (check history)**:
        * "input_type": "identity_query"
        * "conversation": "" # Step 2 will formulate the full identity reply.
        * "original_query": The original current user input text.
        * "contextual_query_interpretation": "User is asking about AI's identity/purpose. Needs full reply from Step 2."

    * **If the query (with context) is a sports or gaming-related query (and not a simple acknowledgment/greeting/out_of_scope)**:
        * "input_type": "sports_query"
        * "sport_id": Numerical ID (Use mapping: {{1: Soccer, ...}}). `null` if unclear.
        * "teams": Array of team names. Empty array ([]) if none.
        * "request_type": String classification (e.g., "scores", "H2H Details", ...).
        * "cc": Dictionary {{ "Team Name": "iso_code" }}. Empty object ({{}}) if none/unknown.
        * "original_query": The original current user input text.
        * "conversation": "" # Step 2 (tool calling) will determine the reply and structure.
        * "contextual_query_interpretation": (Optional) Brief explanation of query interpretation.

    * **If the query is general chit-chat related to sports/gaming, sports trivia, or a conversational follow-up that might need more than a canned reply but doesn't fit sports/identity (and isn't a simple greeting/acknowledgment/out_of_scope)**:
        * "input_type": "conversational"
        * "conversation": "" # Step 2 (tool calling, or direct reply if no tool fits) will formulate the reply.
        * "original_query": current_user_query
        * "contextual_query_interpretation": "General sports/gaming conversational query or trivia for Step 2."

    * **If the query, within the sports/gaming domain, is not recognizable or lacks sufficient information**:
        * "input_type": "invalid_request"
        * "conversation": "I'm not sure how to help with that sports or gaming query. Could you please rephrase or provide more details?"
        * "original_query": current_user_query
        * "contextual_query_interpretation": "Sports/gaming query is unclear or lacks actionable information."

3.  **Be Strict & Context-Aware:** Output ONLY the valid **JSON**. For "out_of_scope_request", "acknowledgment", "simple_greeting", and "invalid_request", the "conversation" field should contain a ready-to-use reply.
"""

FETCH_INFO_PROMPT_TEMPLATE = """
You are a Sports Information Gatherer. Your task is to find factual information related to **sports and gaming queries ONLY**.
Based ONLY on the user's query below (and any provided context if it's a follow-up), provide a comprehensive and informative text answer using your search capabilities.
Focus on facts, statistics, schedules, H2H details, player info, or other pertinent details found that seem relevant to the **sports or gaming query**.
Present the information clearly. Do NOT include any markdown links or URLs in your output. Mention sources by name if absolutely necessary, but do not format them as links.

If the query context indicates it's not a sports or gaming query that requires data fetching (e.g., it's about AI identity, or Step 0 misclassified an out-of-scope query), state "No specific sports/gaming data fetching is required for this query."

User Query Context: "{contextual_interpretation}"
User Query: "{user_query}"
"""

# --- All SCHEMA_DATA_... definitions remain the same ---
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
                    "date": {"type": "string"}, "time": {"type": "string"}, "competition": {"type": "string"}, "round": {"type": "string"},
                    "home_team_name": {"type": "string"}, "away_team_name": {"type": "string"},
                    "score": {"type": "object", "properties": {"fulltime": {"type": "object", "properties": {"home": {"type": ["integer", "null"]}, "away": {"type": ["integer", "null"]}}}, "halftime": {"type": "object", "properties": {"home": {"type": ["integer", "null"]}, "away": {"type": ["integer", "null"]}}}}, "required": ["fulltime"]}, # Corrected: "fulltime" was inside "properties" of "score", it's a direct property of score object
                    "status": {"type": "string"}}, "required": ["date", "home_team_name", "away_team_name", "score", "status"]}}},
    "required": ["matches"]
}
SCHEMA_DATA_MATCH_SCHEDULE_TABLE = {
    "type": "object", "title": "MatchScheduleTableData", "description": "Data for a table of upcoming matches.",
    "properties": {"title": {"type": "string"}, "headers": {"type": "array", "items": {"type": "string"}},
                   "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                   "sort_info": {"type": "string"}},
    "required": ["headers", "rows"]
}
SCHEMA_DATA_TEAM_STATS = {
    "type": "object", "title": "TeamStatsData", "description": "Data for team (or general) statistics.",
    "properties": {"stats_type": {"type": "string"}, "title": {"type": "string"},
                   "sections": {"type": "array", "items": {"type": "object", "properties": {"section_title": {"type": "string"}, "key_value_pairs": {"type": "object", "additionalProperties": {"type": ["string", "number", "null"]}}}, "required": ["section_title", "key_value_pairs"]}},
                   "narrative_summary": {"type": "string"}},
    "required": ["stats_type", "title"]
}
SCHEMA_DATA_STANDINGS_TABLE = {
    "type": "object", "title": "StandingsTableData", "description": "Data for a league standings table.",
    "properties": {"league_name": {"type": "string"}, "season": {"type": "string"},
                   "standings": {"type": "array", "items": {"type": "object", "properties": {
                       "rank": {"type": ["integer", "string"]}, "team_name": {"type": "string"}, "logo_url": {"type": ["string", "null"], "format": "uri"},
                       "played": {"type": "integer"}, "wins": {"type": "integer"}, "draws": {"type": "integer"}, "losses": {"type": "integer"},
                       "goals_for": {"type": "integer"}, "goals_against": {"type": "integer"}, "goal_difference": {"type": "integer"}, "points": {"type": "integer"},
                       "form": {"type": "string"}}, "required": ["rank", "team_name", "played", "points"]}}},
    "required": ["league_name", "standings"]
}
SCHEMA_DATA_SUGGESTION_CARD = {
    "type": "object", "title": "SuggestionCardData", "description": "Data for suggestions or predictions.",
    "properties": {"title": {"type": "string"}, "details": {"type": "string"}, "key_points": {"type": "array", "items": {"type": "string"}},
                   "confidence_level": {"type": ["string", "null"]}, "disclaimer": {"type": "string", "default": "This is based on statistical analysis and not a guarantee."}},
    "required": ["title", "details"]
}
SCHEMA_DATA_PERCENTAGE_CARD = {
    "type": "object", "title": "PercentageCardData", "description": "Data for displaying a specific percentage.",
    "properties": {"title": {"type": "string"}, "value": {"type": "string", "pattern": "^\\d{1,3}(\\.\\d+)?%$"}, "context": {"type": "string"}, "basis": {"type": "string"},
                   "supporting_stats": {"type": "object", "additionalProperties": {"type": ["string", "number"]}}},
    "required": ["title", "value", "context"]
}
SCHEMA_DATA_LIVE_MATCH_DETAILS = {
    "type": "object", "title": "LiveMatchDetailsData", "description": "Data for a currently ongoing live match.",
    "properties": {"match_id": {"type": "string"}, "competition": {"type": "string"}, "home_team_name": {"type": "string"}, "away_team_name": {"type": "string"},
                   "home_team_score": {"type": "integer"}, "away_team_score": {"type": "integer"}, "current_minute": {"type": "string"}, "status_description": {"type": "string"},
                   "key_events": {"type": "array", "items": {"type": "object", "properties": {"minute": {"type": "string"}, "type": {"type": "string", "enum": ["goal", "yellow_card", "red_card", "substitution", "var_decision"]}, "player_name": {"type": "string"}, "team_name": {"type": "string"}, "detail": {"type": "string"}}, "required": ["minute", "type", "team_name"]}},
                   "live_stats": {"type": "object", "properties": {"home_possession": {"type": ["integer", "null"]}, "away_possession": {"type": ["integer", "null"]}, "home_shots": {"type": ["integer", "null"]}, "away_shots": {"type": ["integer", "null"]}, "home_shots_on_target": {"type": ["integer", "null"]}, "away_shots_on_target": {"type": ["integer", "null"]}, "home_corners": {"type": ["integer", "null"]}, "away_corners": {"type": ["integer", "null"]}}}},
    "required": ["competition", "home_team_name", "away_team_name", "home_team_score", "away_team_score", "current_minute", "status_description"]
}
SCHEMA_DATA_MATCH_LINEUPS = {
    "type": "object", "title": "MatchLineupsData", "description": "Lineup information for a specific match.",
    "properties": {"match_description": {"type": "string"},
                   "home_team": {"type": "object", "properties": {"name": {"type": "string"}, "formation": {"type": "string"}, "manager": {"type": ["string", "null"]}, "starting_xi": {"type": "array", "items": {"type": "object", "properties": {"player_name": {"type": "string"}, "jersey_number": {"type": ["integer", "null"]}, "position": {"type": ["string", "null"]}}}}, "substitutes": {"type": "array", "items": {"type": "object", "properties": {"player_name": {"type": "string"}, "jersey_number": {"type": ["integer", "null"]}, "position": {"type": ["string", "null"]}}}}}, "required": ["name", "starting_xi"]},
                   "away_team": {"type": "object", "properties": {"name": {"type": "string"}, "formation": {"type": "string"}, "manager": {"type": ["string", "null"]}, "starting_xi": {"type": "array", "items": {"type": "object", "properties": {"player_name": {"type": "string"}, "jersey_number": {"type": ["integer", "null"]}, "position": {"type": ["string", "null"]}}}}, "substitutes": {"type": "array", "items": {"type": "object", "properties": {"player_name": {"type": "string"}, "jersey_number": {"type": ["integer", "null"]}, "position": {"type": ["string", "null"]}}}}}, "required": ["name", "starting_xi"]}},
    "required": ["match_description", "home_team", "away_team"]
}
SCHEMA_DATA_TOP_PERFORMERS = {
    "type": "object", "title": "TopPerformersData", "description": "Lists top performing players in a specific statistic for a league/tournament.",
    "properties": {"league_name": {"type": "string"}, "season": {"type": "string"}, "statistic_type": {"type": "string"},
                   "performers": {"type": "array", "items": {"type": "object", "properties": {"rank": {"type": "integer"}, "player_name": {"type": "string"}, "team_name": {"type": "string"}, "value": {"type": ["integer", "string"]}, "nationality": {"type": ["string", "null"]}}, "required": ["rank", "player_name", "team_name", "value"]}}},
    "required": ["league_name", "statistic_type", "performers"]
}
SCHEMA_DATA_PLAYER_PROFILE = {
    "type": "object", "title": "PlayerProfileData", "description": "Detailed profile information for a specific player.",
    "properties": {"full_name": {"type": "string"}, "common_name": {"type": ["string", "null"]}, "nationality": {"type": "string"}, "date_of_birth": {"type": "string", "format": "date"}, "age": {"type": "integer"}, "primary_position": {"type": "string"}, "secondary_positions": {"type": "array", "items": {"type": "string"}}, "current_club_name": {"type": ["string", "null"]}, "jersey_number": {"type": ["integer", "string", "null"]}, "height_cm": {"type": ["integer", "null"]}, "weight_kg": {"type": ["integer", "null"]}, "preferred_foot": {"type": ["string", "null"], "enum": [None, "Right", "Left", "Both"]},
                   "career_summary_stats": {"type": "object", "properties": {"appearances": {"type": ["integer", "null"]}, "goals": {"type": ["integer", "null"]}, "assists": {"type": ["integer", "null"]}}},
                   "market_value": {"type": ["string", "null"]}},
    "required": ["full_name", "nationality", "date_of_birth", "primary_position"]
}
SCHEMA_DATA_PLAYER_COMPARISON = {
    "type": "object", "title": "PlayerComparisonData", "description": "Side-by-side comparison of statistics for two or more players.",
    "properties": {"comparison_title": {"type": "string"},
                   "players": {"type": "array", "minItems": 2, "items": {"type": "object", "properties": {"player_name": {"type": "string"}, "team_name": {"type": ["string", "null"]}, "stats": {"type": "object", "additionalProperties": {"type": ["string", "number", "null"]}}}, "required": ["player_name", "stats"]}},
                   "comparison_period": {"type": "string"}},
    "required": ["comparison_title", "players"]
}
SCHEMA_DATA_SPORTS_TERM_EXPLANATION = {
    "type": "object", "title": "SportsTermExplanationData", "description": "Explanation of a sports-related term or rule.",
    "properties": {"term": {"type": "string"}, "explanation": {"type": "string"}, "sport": {"type": ["string", "null"]},
                   "related_terms": {"type": "array", "items": {"type": "string"}}},
    "required": ["term", "explanation"]
}
SCHEMA_DATA_TEAM_NEWS = {
    "type": "object", "title": "TeamNewsData", "description": "Latest news articles or summaries for a specific team.",
    "properties": {"team_name": {"type": "string"},
                   "news_articles": {"type": "array", "items": {"type": "object", "properties": {"title": {"type": "string"}, "source_name": {"type": "string"}, "published_date": {"type": "string", "format": "date-time"}, "url": {"type": "string", "format": "uri"}, "summary": {"type": "string"}}, "required": ["title", "source_name", "published_date", "url"]}}},
    "required": ["team_name", "news_articles"]
}
SCHEMA_DATA_LEAGUE_NEWS = {
    "type": "object", "title": "LeagueNewsData", "description": "Latest news articles or summaries for a specific league.",
    "properties": {"league_name": {"type": "string"},
                   "news_articles": {"type": "array", "items": {"type": "object", "properties": {"title": {"type": "string"}, "source_name": {"type": "string"}, "published_date": {"type": "string", "format": "date-time"}, "url": {"type": "string", "format": "uri"}, "summary": {"type": "string"}}, "required": ["title", "source_name", "published_date", "url"]}}},
    "required": ["league_name", "news_articles"]
}
# --- Tool Definitions (ensure this is up-to-date) ---
TOOLS_AVAILABLE = [
    {"type": "function", "function": {"name": "present_h2h_comparison", "description": "Presents a head-to-head comparison between two teams.", "parameters": SCHEMA_DATA_H2H}},
    {"type": "function", "function": {"name": "display_standings_table", "description": "Displays a league standings table.", "parameters": SCHEMA_DATA_STANDINGS_TABLE}},
    {"type": "function", "function": {"name": "show_match_schedule", "description": "Shows a schedule of upcoming matches.", "parameters": SCHEMA_DATA_MATCH_SCHEDULE_TABLE}},
    {"type": "function", "function": {"name": "list_match_results", "description": "Lists recent match results.", "parameters": SCHEMA_DATA_RESULTS_LIST}},
    {"type": "function", "function": {"name": "provide_team_statistics", "description": "Provides statistics for a team or a general statistical overview.", "parameters": SCHEMA_DATA_TEAM_STATS}},
    {"type": "function", "function": {"name": "offer_suggestion", "description": "Offers a suggestion or prediction based on data.", "parameters": SCHEMA_DATA_SUGGESTION_CARD}},
    {"type": "function", "function": {"name": "analyze_percentage", "description": "Provides an analysis for a percentage-based query.", "parameters": SCHEMA_DATA_PERCENTAGE_CARD}},
    {"type": "function", "function": {"name": "get_live_match_details", "description": "Provides real-time details for an ongoing match.", "parameters": SCHEMA_DATA_LIVE_MATCH_DETAILS}},
    {"type": "function", "function": {"name": "get_match_lineups", "description": "Provides starting lineups and substitutes for a match.", "parameters": SCHEMA_DATA_MATCH_LINEUPS}},
    {"type": "function", "function": {"name": "get_top_performers", "description": "Lists top performing players (e.g., scorers, assists) for a league/tournament.", "parameters": SCHEMA_DATA_TOP_PERFORMERS}},
    {"type": "function", "function": {"name": "get_player_profile", "description": "Retrieves detailed information about a sports player.", "parameters": SCHEMA_DATA_PLAYER_PROFILE}},
    {"type": "function", "function": {"name": "compare_players", "description": "Provides a side-by-side statistical comparison of players.", "parameters": SCHEMA_DATA_PLAYER_COMPARISON}},
    {"type": "function", "function": {"name": "clarify_sports_term", "description": "Explains a specific sports term, rule, or concept.", "parameters": SCHEMA_DATA_SPORTS_TERM_EXPLANATION}},
    {"type": "function", "function": {"name": "get_team_news", "description": "Fetches latest news articles for a specific team.", "parameters": SCHEMA_DATA_TEAM_NEWS}},
    {"type": "function", "function": {"name": "get_league_news", "description": "Fetches latest news articles for a specific league.", "parameters": SCHEMA_DATA_LEAGUE_NEWS}},
]
TOOL_NAME_TO_COMPONENT_TYPE = {
    "present_h2h_comparison": "h2h_comparison_table",
    "display_standings_table": "standings_table",
    "show_match_schedule": "match_schedule_table",
    "list_match_results": "results_list",
    "provide_team_statistics": "team_stats",
    "offer_suggestion": "suggestion_card",
    "analyze_percentage": "percentage_card",
    "get_live_match_details": "live_match_feed",
    "get_match_lineups": "match_lineups_display",
    "get_top_performers": "top_performers_list",
    "get_player_profile": "player_profile_card",
    "compare_players": "player_comparison_view",
    "clarify_sports_term": "term_explanation_box",
    "get_team_news": "news_article_list",
    "get_league_news": "news_article_list",
}
# --- Helper Functions ---
def safeText(text: Any) -> str:
    if text is None or isinstance(text, (dict, list)): return 'N/A'
    text_str = str(text); return html.escape(text_str)

# --- AI Service Core Functions ---
# Step 0: Extract Intent/Entities
async def extract_sports_info(user_query: str, conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
    # Using SYSTEM_PROMPT_EXTRACTOR_V3_2
    # (Logic remains the same as previously provided, ensure V3_2 prompt is used)
    if not user_query: return {"input_type": "invalid_request", "conversation": "", "original_query": ""} #
    fallback_error = {"input_type": "error", "message": "Extraction failed", "original_query": user_query} #

    messages = [{"role": "system", "content": SYSTEM_PROMPT_EXTRACTOR_V3_2}] # Use V3.2
    history_to_include = conversation_history[-4:] #
    for turn in history_to_include: #
        content = turn.get("content") #
        if not isinstance(content, str): #
            content = str(content) #
        messages.append({"role": turn["role"], "content": content}) #
    messages.append({"role": "user", "content": user_query}) #

    try: #
        print(f">>> Attempting extraction call (GPT-3.5 Turbo, JSON Mode, V3.2 Prompt)...") #
        response = await client.chat.completions.create( #
            model="gpt-3.5-turbo-0125", #
            messages=messages, #
            response_format={"type": "json_object"}, #
            temperature=0.2 #
        ) #
        extracted_data = json.loads(response.choices[0].message.content) #
        
        if "original_query" not in extracted_data: #
            extracted_data["original_query"] = user_query #
        if "input_type" not in extracted_data: #
            extracted_data["input_type"] = "unknown" #
            print(f"!!! WARNING: input_type missing from extraction: {extracted_data}") #
        # Ensure conversation field is appropriately set for direct reply types
        if extracted_data.get("input_type") in ["acknowledgment", "simple_greeting", "identity_query", "conversational", "invalid_request", "out_of_scope_request"]: #
            if "conversation" not in extracted_data or not extracted_data.get("conversation","").strip(): #
                 # Default conversation text based on type if not provided by LLM
                default_conversations = {
                    "simple_greeting": "Hello! I'm SPAI. How can I help with sports or gaming info?",
                    "invalid_request": "I'm not sure how to help with that sports query. Could you rephrase?",
                    "out_of_scope_request": "I specialize in sports and gaming information. I can't assist with that topic.",
                    "acknowledgment": "Okay.",
                    "identity_query": "", # To be filled by Step 2
                    "conversational": ""  # To be filled by Step 2
                }
                extracted_data["conversation"] = default_conversations.get(extracted_data.get("input_type"), user_query if extracted_data.get("input_type") not in ["identity_query", "conversational"] else "")


        print(f"Extracted data from Step 0: {json.dumps(extracted_data, indent=2)}") #
        return extracted_data #
    except json.JSONDecodeError as json_err: #
        print(f"JSON decoding error during extraction: {json_err}") #
        raw_output = response.choices[0].message.content if 'response' in locals() and response.choices else 'No response content for extraction' #
        print(f"Raw LLM output (extraction): {raw_output}") #
        fallback_error["message"] = "Failed to parse extraction response" #
        return fallback_error #
    except openai.APIError as api_err: #
        print(f"!!! OPENAI API ERROR during extraction !!! Error details: {api_err}") #
        fallback_error["message"] = str(api_err) #
        return fallback_error #
    except Exception as e: #
        print(f"An error occurred during extraction: {e}") #
        traceback.print_exc() #
        fallback_error["message"] = str(e) #
        return fallback_error #


# Step 1: Fetch Raw Text Data
async def fetch_raw_text_data(user_query: str, parsed_data: Optional[Dict[str, Any]], conversation_history: List[Dict[str, str]]) -> str:
    # (Logic remains the same as previously provided, using FETCH_INFO_PROMPT_TEMPLATE with its domain enforcement)
    input_type = parsed_data.get("input_type") if parsed_data else "unknown" #
    
    no_fetch_types = ["simple_greeting", "acknowledgment", "invalid_request", "identity_query", "out_of_scope_request"] # Add out_of_scope
    request_type = parsed_data.get("request_type") if parsed_data else None #

    if input_type in no_fetch_types: #
         print(f">>> Skipping raw text data fetch: Input type '{input_type}' does not require fetching.") #
         return "--NO DATA FETCHED (Input Type Not Requiring Fetch)--" #
    
    if input_type != "sports_query" and not (input_type == "conversational" and "trivia" in parsed_data.get("contextual_query_interpretation","").lower()): #
        allowed_fetch_request_types = ["suggestion", "percentage_request", "scores", "H2H Details", "lineups", "standings", "match_schedule", "results", "statistics"] # Be more explicit
        if not request_type or request_type not in allowed_fetch_request_types : #
            print(f">>> Skipping raw text data fetch: Input type '{input_type}' (request: {request_type}) not marked for direct fetching.") #
            return "--NO DATA FETCHED (Input Type Not Prioritized For Fetch)--" #

    if not parsed_data: #
        print(">>> Skipping raw text data fetch: Parsed data is missing.") #
        return "--NO DATA FETCHED (Missing Parsed Data)--" #

    query_for_fetch = parsed_data.get("original_query", user_query) #
    contextual_interpretation = parsed_data.get("contextual_query_interpretation", "") #
    
    effective_query_for_fetch = query_for_fetch #
    if contextual_interpretation and "User asked:" not in contextual_interpretation: #
        if len(contextual_interpretation) > len(query_for_fetch) + 10 or not query_for_fetch.startswith(contextual_interpretation): #
             effective_query_for_fetch = f"Context from prior analysis: {contextual_interpretation}\nUser's current query: {query_for_fetch}" #
    
    try: #
        prompt = FETCH_INFO_PROMPT_TEMPLATE.format( #
            user_query=query_for_fetch,  #
            contextual_interpretation=contextual_interpretation #
        ) #
    except Exception as fmt_e: #
         print(f"!!! UNEXPECTED ERROR during data fetch prompt formatting !!! Error: {fmt_e}") #
         return f"--PROMPT FORMATTING ERROR: {fmt_e}--" #

    messages_for_fetch = [{"role": "system", "content": prompt}] #
    history_for_fetch = conversation_history[-2:]  #
    for turn in history_for_fetch: #
        content = turn.get("content") #
        if not isinstance(content, str): content = str(content) #
        if len(content) < 500: #
             messages_for_fetch.append({"role": turn["role"], "content": content}) #

    try: #
        print(f">>> Attempting Search LLM call for raw text data (Input type: {input_type}, Request type hint: {request_type}). Effective Query: {effective_query_for_fetch[:150]}...") #
        response = await client.chat.completions.create( #
            model="gpt-4o-search-preview", #
            messages=messages_for_fetch, #
            temperature=0.3 #
        ) #
        raw_data_string = response.choices[0].message.content.strip() #
        print(f">>> Raw Text Data Received (first 300 chars):\n----------\n{raw_data_string[:300]}...\n----------") #
        if not raw_data_string or \
           (len(raw_data_string) < 70 and ("sorry" in raw_data_string.lower() or \
                                            "don't have specific information" in raw_data_string.lower() or \
                                            "No specific sports/gaming data fetching is required" in raw_data_string or \
                                            "cannot assist with that topic" in raw_data_string.lower())): # Check for fetch refusal
            return f"--FETCH FAILED OR REFUSED: {raw_data_string}--" #
        return raw_data_string #
    except openai.APIError as api_err: print(f"!!! OPENAI API ERROR during raw text data fetch !!! Error details: {api_err}"); return f"--API ERROR: {api_err}--" #
    except Exception as e: print(f"!!! UNEXPECTED EXCEPTION during raw text data fetch !!! Type: {type(e)}, Details: {e}"); traceback.print_exc(); return f"--UNEXPECTED ERROR: {e}--" #


# Step 2: Generate Reply and Structured UI Data via Tool Calling
async def get_structured_data_and_reply_via_tools(
    parsed_data: Dict[str, Any],
    conversation_history: List[Dict[str, str]],
    raw_text_data: str
) -> Dict[str, Any]:
    original_query = parsed_data.get("original_query", "N/A")
    contextual_interpretation = parsed_data.get("contextual_query_interpretation", "N/A")
    input_type_step0 = parsed_data.get("input_type", "unknown")
    request_type_step0 = parsed_data.get("request_type", "N/A")

    tool_system_prompt = """
    You are SPAI (Select Punters AI bot), a specialized AI assistant designed to provide **sports and gaming-related** data, statistics, and insights.
    Your knowledge and capabilities are strictly limited to these domains (sports, e-sports, relevant betting statistics based on historical data or public odds IF specifically asked for analysis).
    
    CRITICALLY IMPORTANT: Your textual reply to the user ('final_reply') MUST NOT contain any markdown links (e.g., `[text](URL)`), full URLs, or hyperlinks. If you need to mention a source or an entity, refer to it by its name ONLY. Do not attempt to make text clickable or suggest searching elsewhere.

    Analyze the user's query and context.
    1. If the query is clearly outside your sports/gaming domain (e.g., math help, medical advice), politely state your specialization and indicate you cannot help with that specific off-topic request. Do NOT attempt to answer it.
    2. If the query is within your sports/gaming domain:
        a. Select the MOST appropriate tool from the available list to structure and present the data if applicable.
        b. Formulate a concise, user-facing textual reply. If you use a tool, this reply should introduce or summarize the data presented by the tool.
        c. If no specific tool is suitable for structuring data, but the query is a valid sports/gaming conversational topic or trivia, provide a direct textual reply.
    """
    
    messages = [{"role": "system", "content": tool_system_prompt}]
    for turn in conversation_history[-3:]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    user_context_for_tool_call = f"""
    Original User Query: {original_query}
    My Initial Analysis (from Step 0):
      Input Type: {input_type_step0}
      Request Type: {request_type_step0}
      Contextual Interpretation: {contextual_interpretation}
    
    Information Gathered (from Step 1 for sports queries):
    ```text
    {raw_text_data if raw_text_data and not raw_text_data.startswith("--") else "No specific data was fetched, or the query was not data-oriented (e.g., conversational, identity)."}
    ```
    Based on all this, proceed according to your instructions (decline off-topic, use a tool for sports data, or reply directly for sports conversation).
    Remember: NO LINKS in your textual reply.
    """
    messages.append({"role": "user", "content": user_context_for_tool_call})

    final_reply = "I've processed your request on sports and gaming."
    ui_data = {"component_type": "generic_text", "data": {"message": "Please ask a sports or gaming related question."}}

    # If Step 0 already determined it's out of scope, we should use that reply.
    # This function (Step 2) should ideally not be called for out_of_scope_request if short-circuiting works.
    # However, as a fallback:
    if input_type_step0 == "out_of_scope_request":
        return {
            "reply": parsed_data.get("conversation", "I specialize in sports and gaming information and cannot assist with that topic."),
            "ui_data": {"component_type": "generic_text", "data": {"message": "Request outside of sports/gaming domain."}}
        }

    try:
        print(f">>> Attempting LLM call with Tools (Model: gpt-4o). Input Type from Step 0: {input_type_step0}")
        response = await client.chat.completions.create(
            model="gpt-4o", 
            messages=messages,
            tools=TOOLS_AVAILABLE,
            tool_choice="auto", 
            temperature=0.3 # Lower temp for more focused tool use and factual replies
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if response_message.content:
            final_reply = response_message.content
            # Final check for links in LLM's direct reply - this is a bit crude, better handled by prompt.
            if "http:" in final_reply or "https:" in final_reply or "[" in final_reply and "](" in final_reply:
                print("!!! WARNING: LLM direct reply contained potential links, attempting to mitigate. Prompt needs to be stricter.")
                # Simple mitigation: just state that info was processed. A more complex regex could remove links.
                # For now, rely on strong prompting. If it still happens, a post-processing step might be needed.
                # final_reply = "I have processed your request and have some information for you." # Overwrite if links are found
        
        if tool_calls:
            # (Tool processing logic as before)
            print(f">>> Tool calls received: {len(tool_calls)}. Processing the first one.") #
            tool_call = tool_calls[0]  #
            function_name = tool_call.function.name #
            function_args_json = tool_call.function.arguments #
            
            print(f"  Tool to call: {function_name}") #
            print(f"  Tool arguments (raw JSON string): {function_args_json[:200]}...") #

            try: #
                function_args = json.loads(function_args_json) #
                ui_data["component_type"] = TOOL_NAME_TO_COMPONENT_TYPE.get(function_name, function_name) #
                ui_data["data"] = function_args #

                if not response_message.content: #
                    component_name_readable = ui_data['component_type'].replace('_', ' ').title() #
                    final_reply = f"Okay, here is the {component_name_readable} you requested." #
                print(f"  Successfully parsed arguments for tool {function_name}.") #

            except json.JSONDecodeError as json_decode_err: #
                print(f"!!! ERROR: Failed to parse tool arguments JSON for {function_name}: {json_decode_err}") #
                print(f"  Faulty JSON string was: {function_args_json}") #
                current_reply_prefix = final_reply if response_message.content else "I found the information, but "
                final_reply = current_reply_prefix + "there was an issue structuring it for display." #
                ui_data = {"component_type": "generic_text", "data": {"error": "Failed to parse structured data from AI.", "tool_name": function_name}} #
        
        elif not response_message.content:
            print("!!! LLM made no tool call and provided no direct reply content.") #
            if raw_text_data.startswith("--FETCH FAILED") or (raw_text_data.startswith("--NO DATA") and input_type_step0 == "sports_query"): #
                final_reply = "I couldn't find the specific information for your sports query at the moment." #
            else: #
                final_reply = "I've processed your query. Is there anything else sports or gaming related I can help with?" #

        # Ensure no links in the final reply, even if LLM was directly conversational
        # This is a fallback, strong prompting is preferred.
        if re.search(r"\[.*?\]\(http[s]?://.*?\)|http[s]?://\S+", final_reply):
            print("!!! WARNING: Final reply contained links AFTER tool processing. Overwriting with generic message or attempting cleanup.")
            # Simplistic cleanup, might remove valid text. A proper HTML/Markdown stripper would be better if this is frequent.
            final_reply = re.sub(r"\[.*?\]\(http[s]?://.*?\)", "[link removed]", final_reply)
            final_reply = re.sub(r"http[s]?://\S+", "https://www.merriam-webster.com/dictionary/removed", final_reply)
            final_reply += " (Note: Links have been removed as per policy)."


        return {"reply": final_reply, "ui_data": ui_data}

    except openai.APIError as api_err: #
        print(f"!!! OPENAI API ERROR with Tool Calling !!! Error Details: {api_err}") #
        return {"reply": f"An API error occurred while processing your request ({api_err.code}). Please try again.",  #
                "ui_data": {"component_type": "generic_text", "data": {"error": str(api_err)}}} #
    except Exception as e: #
        print(f"!!! UNEXPECTED EXCEPTION during Tool Calling or final processing !!! Type: {type(e)}, Details: {e}") #
        traceback.print_exc() #
        return {"reply": "I encountered an unexpected internal issue. Please try asking in a different way.",  #
                "ui_data": {"component_type": "generic_text", "data": {"error": str(e)}}} #