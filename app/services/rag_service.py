# app/services/rag_service.py

from app.api.openai_service import get_chat_completion
from app.prompts.prompt_templates import PROMPT_TEMPLATE
from app.utils.helpers import format_api_data_as_context
from app.api import rapidapi_service

def generate_chat_response(user_message: str) -> str:
    """
    Generates a chat response by:
    1. Retrieving and formatting context from API data.
    2. Building a prompt using a template.
    3. Calling the OpenAI API for a completion.
    """
    # Example: Use the rapidapi_service to get the latest matches for a team mentioned in the query.
    # For simplicity, we assume the query contains a team name.
    # In production, you might add more sophisticated entity extraction.
    team = user_message.split()[0]  # Simple assumption: first word is a team name.
    api_data = rapidapi_service.get_last_matches(team)
    
    # Format the API data as context.
    context = format_api_data_as_context(api_data)
    
    # Build the prompt.
    prompt = PROMPT_TEMPLATE.format(context=context, query=user_message)
    
    # Get a completion from OpenAI.
    response = get_chat_completion(prompt)
    
    return response
