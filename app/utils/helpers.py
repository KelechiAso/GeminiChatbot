# app/utils/helpers.py

def format_api_data_as_context(api_data: dict) -> str:
    """
    Converts API JSON data into a plain-text context summary.
    This is a simple implementation; adjust it to your data structure.
    """
    if not api_data or "error" in api_data:
        return "No relevant data available."
    
    response = api_data.get("response", [])
    if not response:
        return "No recent matches found."
    
    # Create a summary of the first few fixtures.
    context_lines = []
    for fixture in response[:3]:
        teams = fixture.get("teams", {})
        home_team = teams.get("home", {}).get("name", "Unknown")
        away_team = teams.get("away", {}).get("name", "Unknown")
        score = fixture.get("score", {}).get("fulltime", {})
        home_score = score.get("home", "?")
        away_score = score.get("away", "?")
        date_ts = fixture.get("fixture", {}).get("timestamp", 0)
        from datetime import datetime
        date_str = datetime.utcfromtimestamp(date_ts).strftime("%Y-%m-%d")
        context_lines.append(f"On {date_str}, {home_team} {home_score} - {away_score} {away_team}.")
    
    return "\n".join(context_lines)
