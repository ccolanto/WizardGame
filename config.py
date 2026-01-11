"""
Configuration settings for the Wizard Card Game.
Toggle between local (JSON) and cloud (Firestore) modes.
"""

# =============================================================================
# PHASE CONFIGURATION
# =============================================================================
# Set to "local" for Phase 1 (JSON file database)
# Set to "firestore" for Phase 2/3 (Google Firestore)
DATABASE_MODE = "local"

# =============================================================================
# GAME SETTINGS
# =============================================================================
MIN_PLAYERS = 2
MAX_PLAYERS = 6
CARDS_PER_PLAYER_ROUND_1 = 1  # Cards dealt increases each round

# =============================================================================
# AUTO-REFRESH SETTINGS
# =============================================================================
# How often to check for game state updates (in seconds)
REFRESH_INTERVAL = 2

# =============================================================================
# LOCAL DATABASE SETTINGS (Phase 1)
# =============================================================================
LOCAL_DB_PATH = "game_state.json"

# =============================================================================
# FIRESTORE SETTINGS (Phase 2/3)
# =============================================================================
# For Streamlit Cloud, these will come from secrets
# For local testing with Firestore, set your credentials path
FIRESTORE_CREDENTIALS_PATH = "firebase_credentials.json"
FIRESTORE_COLLECTION = "wizard_games"
