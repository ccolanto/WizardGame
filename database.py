"""
Database abstraction layer.
Supports local JSON file (Phase 1) and Google Firestore (Phase 2/3).
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from game_logic import GameState
import config


class DatabaseInterface(ABC):
    """Abstract base class for database operations."""
    
    @abstractmethod
    def save_game(self, game_state: GameState) -> bool:
        """Save game state to database."""
        pass
    
    @abstractmethod
    def load_game(self, game_id: str) -> Optional[GameState]:
        """Load game state from database."""
        pass
    
    @abstractmethod
    def delete_game(self, game_id: str) -> bool:
        """Delete a game from database."""
        pass
    
    @abstractmethod
    def list_games(self) -> list[str]:
        """List all active game IDs."""
        pass
    
    @abstractmethod
    def get_last_updated(self, game_id: str) -> Optional[str]:
        """Get the last updated timestamp for a game (for efficient polling)."""
        pass


class LocalJSONDatabase(DatabaseInterface):
    """
    Phase 1: Local JSON file database.
    Stores all games in a single JSON file for simplicity.
    """
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or config.LOCAL_DB_PATH
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create the JSON file if it doesn't exist."""
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({"games": {}}, f)
    
    def _read_all(self) -> dict:
        """Read all data from the JSON file."""
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"games": {}}
    
    def _write_all(self, data: dict):
        """Write all data to the JSON file."""
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def save_game(self, game_state: GameState) -> bool:
        """Save game state to JSON file."""
        try:
            data = self._read_all()
            game_state.last_updated = datetime.now().isoformat()
            data["games"][game_state.game_id] = game_state.to_dict()
            self._write_all(data)
            return True
        except Exception as e:
            print(f"Error saving game: {e}")
            return False
    
    def load_game(self, game_id: str) -> Optional[GameState]:
        """Load game state from JSON file."""
        try:
            data = self._read_all()
            if game_id in data["games"]:
                return GameState.from_dict(data["games"][game_id])
            return None
        except Exception as e:
            print(f"Error loading game: {e}")
            return None
    
    def delete_game(self, game_id: str) -> bool:
        """Delete a game from JSON file."""
        try:
            data = self._read_all()
            if game_id in data["games"]:
                del data["games"][game_id]
                self._write_all(data)
            return True
        except Exception as e:
            print(f"Error deleting game: {e}")
            return False
    
    def list_games(self) -> list[str]:
        """List all active game IDs."""
        data = self._read_all()
        return list(data["games"].keys())
    
    def get_last_updated(self, game_id: str) -> Optional[str]:
        """Get the last updated timestamp."""
        data = self._read_all()
        if game_id in data["games"]:
            return data["games"][game_id].get("last_updated")
        return None


class FirestoreDatabase(DatabaseInterface):
    """
    Phase 2/3: Google Firestore database.
    Provides real-time updates and cloud persistence.
    """
    
    def __init__(self):
        self.db = None
        self.collection_name = config.FIRESTORE_COLLECTION
        self._initialize_firestore()
    
    def _initialize_firestore(self):
        """Initialize Firestore connection."""
        try:
            import streamlit as st
            from google.cloud import firestore
            from google.oauth2 import service_account
            
            # Try to get credentials from Streamlit secrets first (for cloud deployment)
            if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
                credentials = service_account.Credentials.from_service_account_info(
                    st.secrets["gcp_service_account"]
                )
                self.db = firestore.Client(credentials=credentials)
            elif os.path.exists(config.FIRESTORE_CREDENTIALS_PATH):
                # Local development with credentials file
                credentials = service_account.Credentials.from_service_account_file(
                    config.FIRESTORE_CREDENTIALS_PATH
                )
                self.db = firestore.Client(credentials=credentials)
            else:
                print("Warning: No Firestore credentials found. Falling back to local database.")
                self.db = None
                
        except ImportError:
            print("Warning: google-cloud-firestore not installed. Using local database.")
            self.db = None
        except Exception as e:
            print(f"Error initializing Firestore: {e}")
            self.db = None
    
    def save_game(self, game_state: GameState) -> bool:
        """Save game state to Firestore."""
        if not self.db:
            return False
        
        try:
            game_state.last_updated = datetime.now().isoformat()
            doc_ref = self.db.collection(self.collection_name).document(game_state.game_id)
            doc_ref.set(game_state.to_dict())
            return True
        except Exception as e:
            print(f"Error saving to Firestore: {e}")
            return False
    
    def load_game(self, game_id: str) -> Optional[GameState]:
        """Load game state from Firestore."""
        if not self.db:
            return None
        
        try:
            doc_ref = self.db.collection(self.collection_name).document(game_id)
            doc = doc_ref.get()
            if doc.exists:
                return GameState.from_dict(doc.to_dict())
            return None
        except Exception as e:
            print(f"Error loading from Firestore: {e}")
            return None
    
    def delete_game(self, game_id: str) -> bool:
        """Delete a game from Firestore."""
        if not self.db:
            return False
        
        try:
            self.db.collection(self.collection_name).document(game_id).delete()
            return True
        except Exception as e:
            print(f"Error deleting from Firestore: {e}")
            return False
    
    def list_games(self) -> list[str]:
        """List all active game IDs."""
        if not self.db:
            return []
        
        try:
            docs = self.db.collection(self.collection_name).stream()
            return [doc.id for doc in docs]
        except Exception as e:
            print(f"Error listing games from Firestore: {e}")
            return []
    
    def get_last_updated(self, game_id: str) -> Optional[str]:
        """Get the last updated timestamp."""
        if not self.db:
            return None
        
        try:
            doc_ref = self.db.collection(self.collection_name).document(game_id)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict().get("last_updated")
            return None
        except Exception as e:
            print(f"Error getting timestamp from Firestore: {e}")
            return None


def get_database() -> DatabaseInterface:
    """
    Factory function to get the appropriate database based on config.
    """
    if config.DATABASE_MODE == "firestore":
        db = FirestoreDatabase()
        if db.db is not None:
            return db
        # Fall back to local if Firestore initialization failed
        print("Falling back to local database")
    
    return LocalJSONDatabase()
