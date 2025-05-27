# app/__init__.py
from flask import Flask
from app.config import Config
from app.api.bet_api import BetsAPIClient

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Instantiate the Bets API client and attach it to the app
    app.bets_api_client = BetsAPIClient(
        api_key=app.config.get("BETS_API_KEY"),
        base_url=app.config.get("BETS_API_HOST")
    )
    
    # Register blueprints, etc.
    from app.routes.chat_routes import chat_bp
    app.register_blueprint(chat_bp)
    
    return app
