# app/config.py

import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

class Config:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "YOUR-RAPIDAPI-KEY")  # Default value if not in env
    FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
    POPULAR_LEAGUE_IDS = [
        39,   # Premier League
        140,  # La Liga
        61,   # Ligue 1
        78,   # Bundesliga
        135,  # Serie A
        # Add more as needed
    ]
    SPORT_ID = 1

# Load configuration
config = Config()