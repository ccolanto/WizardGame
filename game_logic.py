"""
Game Logic for the Wizard Card Game.
Contains all core game mechanics: cards, deck, tricks, scoring, and game state management.
"""

import random
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import json
from datetime import datetime


class Suit(Enum):
    """Card suits - Wizard and Jester are special suits."""
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"
    WIZARD = "🧙"
    JESTER = "🃏"


class GamePhase(Enum):
    """Current phase of the game."""
    WAITING_FOR_PLAYERS = "waiting_for_players"
    CHOOSING_TRUMP = "choosing_trump"  # Dealer chooses trump when Wizard is flipped
    BIDDING = "bidding"
    PLAYING = "playing"
    TRICK_COMPLETE = "trick_complete"
    ROUND_COMPLETE = "round_complete"
    GAME_OVER = "game_over"


@dataclass
class Card:
    """Represents a single card."""
    suit: Suit
    value: int  # 1-13 for normal cards, 0 for Jester, 14 for Wizard
    
    def __post_init__(self):
        if isinstance(self.suit, str):
            self.suit = Suit(self.suit)
    
    @property
    def display_name(self) -> str:
        """Get display name for the card."""
        if self.suit == Suit.WIZARD:
            return "🧙 Wizard"
        if self.suit == Suit.JESTER:
            return "🃏 Jester"
        
        value_names = {1: "A", 11: "J", 12: "Q", 13: "K"}
        value_str = value_names.get(self.value, str(self.value))
        return f"{value_str}{self.suit.value}"
    
    @property
    def sort_key(self) -> tuple:
        """Key for sorting cards in hand."""
        suit_order = {Suit.WIZARD: 0, Suit.JESTER: 5, 
                      Suit.SPADES: 1, Suit.HEARTS: 2, 
                      Suit.DIAMONDS: 3, Suit.CLUBS: 4}
        return (suit_order.get(self.suit, 6), -self.value)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {"suit": self.suit.value, "value": self.value}
    
    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        """Create card from dictionary."""
        return cls(suit=Suit(data["suit"]), value=data["value"])
    
    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.value == other.value
    
    def __hash__(self):
        return hash((self.suit, self.value))


@dataclass
class Player:
    """Represents a player in the game."""
    player_id: str
    name: str
    hand: list[Card] = field(default_factory=list)
    bid: Optional[int] = None
    tricks_won: int = 0
    score: int = 0
    is_ready: bool = False
    is_connected: bool = True
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "player_id": self.player_id,
            "name": self.name,
            "hand": [card.to_dict() for card in self.hand],
            "bid": self.bid,
            "tricks_won": self.tricks_won,
            "score": self.score,
            "is_ready": self.is_ready,
            "is_connected": self.is_connected
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        """Create player from dictionary."""
        player = cls(
            player_id=data["player_id"],
            name=data["name"],
            bid=data.get("bid"),
            tricks_won=data.get("tricks_won", 0),
            score=data.get("score", 0),
            is_ready=data.get("is_ready", False),
            is_connected=data.get("is_connected", True)
        )
        player.hand = [Card.from_dict(c) for c in data.get("hand", [])]
        return player


@dataclass 
class PlayedCard:
    """A card played to the current trick."""
    player_id: str
    card: Card
    
    def to_dict(self) -> dict:
        return {"player_id": self.player_id, "card": self.card.to_dict()}
    
    @classmethod
    def from_dict(cls, data: dict) -> "PlayedCard":
        return cls(player_id=data["player_id"], card=Card.from_dict(data["card"]))


@dataclass
class ChatMessage:
    """A chat message in the game."""
    player_name: str
    message: str
    timestamp: str
    
    def to_dict(self) -> dict:
        return {"player_name": self.player_name, "message": self.message, "timestamp": self.timestamp}
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(player_name=data["player_name"], message=data["message"], timestamp=data.get("timestamp", ""))


@dataclass
class GameState:
    """Complete state of a game."""
    game_id: str
    host_id: str
    players: list[Player] = field(default_factory=list)
    phase: GamePhase = GamePhase.WAITING_FOR_PLAYERS
    current_round: int = 1
    current_trick: int = 1
    current_player_index: int = 0
    dealer_index: int = 0
    trump_card: Optional[Card] = None
    trump_suit: Optional[Suit] = None
    lead_suit: Optional[Suit] = None
    current_trick_cards: list[PlayedCard] = field(default_factory=list)
    trick_winner: Optional[str] = None
    deck: list[Card] = field(default_factory=list)
    last_updated: str = ""
    message: str = ""
    chat_messages: list[ChatMessage] = field(default_factory=list)
    
    def __post_init__(self):
        if isinstance(self.phase, str):
            self.phase = GamePhase(self.phase)
        if isinstance(self.trump_suit, str):
            self.trump_suit = Suit(self.trump_suit) if self.trump_suit else None
        if isinstance(self.lead_suit, str):
            self.lead_suit = Suit(self.lead_suit) if self.lead_suit else None
    
    @property
    def max_rounds(self) -> int:
        """Calculate maximum rounds based on player count."""
        if len(self.players) == 0:
            return 0
        # 60 cards in deck (52 + 4 wizards + 4 jesters), divide by player count
        return 60 // len(self.players)
    
    @property
    def cards_this_round(self) -> int:
        """Number of cards dealt this round."""
        return self.current_round
    
    @property
    def current_player(self) -> Optional[Player]:
        """Get the current player."""
        if not self.players or self.current_player_index >= len(self.players):
            return None
        return self.players[self.current_player_index]
    
    def get_player(self, player_id: str) -> Optional[Player]:
        """Get a player by ID."""
        for player in self.players:
            if player.player_id == player_id:
                return player
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "game_id": self.game_id,
            "host_id": self.host_id,
            "players": [p.to_dict() for p in self.players],
            "phase": self.phase.value,
            "current_round": self.current_round,
            "current_trick": self.current_trick,
            "current_player_index": self.current_player_index,
            "dealer_index": self.dealer_index,
            "trump_card": self.trump_card.to_dict() if self.trump_card else None,
            "trump_suit": self.trump_suit.value if self.trump_suit else None,
            "lead_suit": self.lead_suit.value if self.lead_suit else None,
            "current_trick_cards": [pc.to_dict() for pc in self.current_trick_cards],
            "trick_winner": self.trick_winner,
            "deck": [c.to_dict() for c in self.deck],
            "last_updated": self.last_updated,
            "message": self.message,
            "chat_messages": [cm.to_dict() for cm in self.chat_messages]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        """Create game state from dictionary."""
        state = cls(
            game_id=data["game_id"],
            host_id=data["host_id"],
            phase=GamePhase(data["phase"]),
            current_round=data.get("current_round", 1),
            current_trick=data.get("current_trick", 1),
            current_player_index=data.get("current_player_index", 0),
            dealer_index=data.get("dealer_index", 0),
            trick_winner=data.get("trick_winner"),
            last_updated=data.get("last_updated", ""),
            message=data.get("message", "")
        )
        state.players = [Player.from_dict(p) for p in data.get("players", [])]
        state.trump_card = Card.from_dict(data["trump_card"]) if data.get("trump_card") else None
        state.trump_suit = Suit(data["trump_suit"]) if data.get("trump_suit") else None
        state.lead_suit = Suit(data["lead_suit"]) if data.get("lead_suit") else None
        state.current_trick_cards = [PlayedCard.from_dict(pc) for pc in data.get("current_trick_cards", [])]
        state.deck = [Card.from_dict(c) for c in data.get("deck", [])]
        state.chat_messages = [ChatMessage.from_dict(cm) for cm in data.get("chat_messages", [])]
        return state


def create_deck() -> list[Card]:
    """Create a complete 60-card Wizard deck."""
    deck = []
    
    # Add 4 Wizards
    for _ in range(4):
        deck.append(Card(suit=Suit.WIZARD, value=14))
    
    # Add 4 Jesters
    for _ in range(4):
        deck.append(Card(suit=Suit.JESTER, value=0))
    
    # Add standard cards (1-13 for each suit)
    for suit in [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
        for value in range(1, 14):
            deck.append(Card(suit=suit, value=value))
    
    return deck


def shuffle_deck(deck: list[Card]) -> list[Card]:
    """Shuffle the deck."""
    shuffled = deck.copy()
    random.shuffle(shuffled)
    return shuffled


def deal_cards(game_state: GameState) -> GameState:
    """Deal cards for the current round."""
    # Create and shuffle deck
    game_state.deck = shuffle_deck(create_deck())
    
    # Clear hands and reset for new round
    for player in game_state.players:
        player.hand = []
        player.bid = None
        player.tricks_won = 0
    
    # Deal cards to each player
    cards_to_deal = game_state.cards_this_round
    for _ in range(cards_to_deal):
        for player in game_state.players:
            if game_state.deck:
                player.hand.append(game_state.deck.pop())
    
    # Sort hands
    for player in game_state.players:
        player.hand.sort(key=lambda c: c.sort_key)
    
    # Flip trump card if cards remain
    if game_state.deck:
        game_state.trump_card = game_state.deck.pop()
        if game_state.trump_card.suit == Suit.WIZARD:
            # Dealer must choose trump - set phase and wait
            game_state.trump_suit = None  # Will be set by dealer
            game_state.phase = GamePhase.CHOOSING_TRUMP
            game_state.message = f"Wizard flipped! {game_state.players[game_state.dealer_index].name} must choose trump suit."
        elif game_state.trump_card.suit == Suit.JESTER:
            game_state.trump_suit = None  # No trump this round
        else:
            game_state.trump_suit = game_state.trump_card.suit
    else:
        game_state.trump_card = None
        game_state.trump_suit = None
    
    # Set first bidder (player after dealer)
    game_state.current_player_index = (game_state.dealer_index + 1) % len(game_state.players)
    game_state.current_trick = 1
    game_state.current_trick_cards = []
    game_state.lead_suit = None
    
    return game_state


def get_forbidden_bid(game_state: GameState) -> int:
    """
    Calculate the forbidden bid for the dealer (screw the dealer rule).
    Returns -1 if no restriction (not the dealer's turn or not all others have bid).
    """
    dealer = game_state.players[game_state.dealer_index]
    current = game_state.current_player
    
    # Only applies to dealer
    if not current or current.player_id != dealer.player_id:
        return -1
    
    # Check if dealer is last to bid
    other_bids = [p.bid for p in game_state.players if p.player_id != dealer.player_id]
    if None in other_bids:
        return -1  # Not all others have bid yet
    
    # Calculate forbidden bid
    total_bid = sum(other_bids)
    tricks_available = game_state.cards_this_round
    forbidden = tricks_available - total_bid
    
    # Only forbid if it's a valid bid option (0 to cards_this_round)
    if 0 <= forbidden <= tricks_available:
        return forbidden
    return -1


def choose_trump(game_state: GameState, player_id: str, suit: Suit) -> GameState:
    """Dealer chooses trump suit when a Wizard is flipped."""
    dealer = game_state.players[game_state.dealer_index]
    
    # Only dealer can choose
    if player_id != dealer.player_id:
        return game_state
    
    # Must be in choosing trump phase
    if game_state.phase != GamePhase.CHOOSING_TRUMP:
        return game_state
    
    game_state.trump_suit = suit
    game_state.phase = GamePhase.BIDDING
    game_state.message = f"{dealer.name} chose {suit.value} as trump! {game_state.current_player.name}'s turn to bid."
    game_state.last_updated = datetime.now().isoformat()
    
    return game_state


def place_bid(game_state: GameState, player_id: str, bid: int) -> GameState:
    """Place a bid for a player."""
    player = game_state.get_player(player_id)
    if not player:
        return game_state
    
    player.bid = bid
    
    # Move to next player
    game_state.current_player_index = (game_state.current_player_index + 1) % len(game_state.players)
    
    # Check if all players have bid
    if all(p.bid is not None for p in game_state.players):
        game_state.phase = GamePhase.PLAYING
        # First player after dealer leads
        game_state.current_player_index = (game_state.dealer_index + 1) % len(game_state.players)
        game_state.message = f"Bidding complete! {game_state.current_player.name}'s turn to lead."
    else:
        game_state.message = f"Waiting for {game_state.current_player.name} to bid."
    
    game_state.last_updated = datetime.now().isoformat()
    return game_state


def get_valid_cards(player: Player, lead_suit: Optional[Suit]) -> list[Card]:
    """Get list of valid cards a player can play."""
    if not lead_suit:
        return player.hand  # First to play can play anything
    
    # Wizards and Jesters can always be played
    special_cards = [c for c in player.hand if c.suit in (Suit.WIZARD, Suit.JESTER)]
    
    # Cards matching lead suit
    matching_cards = [c for c in player.hand if c.suit == lead_suit]
    
    if matching_cards:
        # Must follow suit if possible (but can always play wizard/jester)
        return matching_cards + special_cards
    else:
        # Can play anything if can't follow suit
        return player.hand


def play_card(game_state: GameState, player_id: str, card: Card) -> GameState:
    """Play a card to the current trick."""
    player = game_state.get_player(player_id)
    if not player:
        return game_state
    
    # Remove card from hand
    player.hand = [c for c in player.hand if not (c.suit == card.suit and c.value == card.value)]
    
    # Set lead suit if first card (and not Wizard/Jester)
    if not game_state.current_trick_cards:
        if card.suit not in (Suit.WIZARD, Suit.JESTER):
            game_state.lead_suit = card.suit
        else:
            game_state.lead_suit = None
    elif game_state.lead_suit is None and card.suit not in (Suit.WIZARD, Suit.JESTER):
        # If lead was Jester, first non-special card sets suit
        game_state.lead_suit = card.suit
    
    # Add card to trick
    game_state.current_trick_cards.append(PlayedCard(player_id=player_id, card=card))
    
    # Check if trick is complete
    if len(game_state.current_trick_cards) == len(game_state.players):
        winner_id = determine_trick_winner(game_state)
        winner = game_state.get_player(winner_id)
        winner.tricks_won += 1
        game_state.trick_winner = winner_id
        game_state.phase = GamePhase.TRICK_COMPLETE
        game_state.message = f"{winner.name} wins the trick!"
    else:
        # Move to next player
        game_state.current_player_index = (game_state.current_player_index + 1) % len(game_state.players)
        game_state.message = f"{game_state.current_player.name}'s turn to play."
    
    game_state.last_updated = datetime.now().isoformat()
    return game_state


def determine_trick_winner(game_state: GameState) -> str:
    """Determine the winner of the current trick."""
    # Check for Wizards first (first Wizard played wins)
    for played in game_state.current_trick_cards:
        if played.card.suit == Suit.WIZARD:
            return played.player_id
    
    # If all Jesters, first player wins
    if all(pc.card.suit == Suit.JESTER for pc in game_state.current_trick_cards):
        return game_state.current_trick_cards[0].player_id
    
    lead_suit = game_state.lead_suit
    trump_suit = game_state.trump_suit
    
    winning_played = None
    
    for played in game_state.current_trick_cards:
        card = played.card
        
        # Skip Jesters - they never win
        if card.suit == Suit.JESTER:
            continue
        
        # First non-jester card becomes initial winner
        if winning_played is None:
            winning_played = played
            # If lead_suit wasn't set (all jesters before this), set it now
            if lead_suit is None and card.suit not in (Suit.WIZARD, Suit.JESTER):
                lead_suit = card.suit
            continue
        
        winning_card = winning_played.card
        
        # Determine if current card beats winning card
        current_is_trump = trump_suit and card.suit == trump_suit
        winning_is_trump = trump_suit and winning_card.suit == trump_suit
        current_follows_lead = lead_suit and card.suit == lead_suit
        winning_follows_lead = lead_suit and winning_card.suit == lead_suit
        
        # Trump beats non-trump
        if current_is_trump and not winning_is_trump:
            winning_played = played
        elif winning_is_trump and not current_is_trump:
            # Current card can't beat trump
            pass
        elif current_is_trump and winning_is_trump:
            # Both trump - higher value wins
            if card.value > winning_card.value:
                winning_played = played
        elif current_follows_lead and winning_follows_lead:
            # Both follow lead suit - higher value wins
            if card.value > winning_card.value:
                winning_played = played
        elif current_follows_lead and not winning_follows_lead:
            # Current follows lead, winning doesn't - current wins
            winning_played = played
        # If neither follows lead and neither is trump, first one wins (no change)
    
    return winning_played.player_id if winning_played else game_state.current_trick_cards[0].player_id


def start_next_trick(game_state: GameState) -> GameState:
    """Start the next trick or end the round."""
    game_state.current_trick_cards = []
    game_state.lead_suit = None
    game_state.current_trick += 1
    
    # Check if round is complete
    if game_state.current_trick > game_state.cards_this_round:
        # Calculate scores
        game_state = calculate_round_scores(game_state)
        game_state.phase = GamePhase.ROUND_COMPLETE
    else:
        # Winner of last trick leads
        winner_index = next(i for i, p in enumerate(game_state.players) if p.player_id == game_state.trick_winner)
        game_state.current_player_index = winner_index
        game_state.phase = GamePhase.PLAYING
        game_state.trick_winner = None
        game_state.message = f"Trick {game_state.current_trick}. {game_state.current_player.name} leads."
    
    game_state.last_updated = datetime.now().isoformat()
    return game_state


def calculate_round_scores(game_state: GameState) -> GameState:
    """Calculate and update scores for the round."""
    for player in game_state.players:
        if player.bid == player.tricks_won:
            # Made bid: 20 points + 10 per trick
            player.score += 20 + (10 * player.tricks_won)
        else:
            # Missed bid: -10 per trick off
            player.score -= 10 * abs(player.bid - player.tricks_won)
    
    # Build score message
    score_msgs = []
    for player in game_state.players:
        result = "made" if player.bid == player.tricks_won else "missed"
        score_msgs.append(f"{player.name} bid {player.bid}, won {player.tricks_won} ({result})")
    
    game_state.message = "Round complete! " + " | ".join(score_msgs)
    return game_state


def start_next_round(game_state: GameState) -> GameState:
    """Start the next round or end the game."""
    game_state.current_round += 1
    game_state.dealer_index = (game_state.dealer_index + 1) % len(game_state.players)
    
    if game_state.current_round > game_state.max_rounds:
        game_state.phase = GamePhase.GAME_OVER
        winner = max(game_state.players, key=lambda p: p.score)
        game_state.message = f"Game Over! {winner.name} wins with {winner.score} points!"
    else:
        game_state = deal_cards(game_state)
        game_state.phase = GamePhase.BIDDING
        game_state.message = f"Round {game_state.current_round}. {game_state.current_player.name}'s turn to bid."
    
    game_state.last_updated = datetime.now().isoformat()
    return game_state


def create_new_game(game_id: str, host_id: str, host_name: str) -> GameState:
    """Create a new game."""
    game_state = GameState(
        game_id=game_id,
        host_id=host_id,
        last_updated=datetime.now().isoformat()
    )
    
    host_player = Player(player_id=host_id, name=host_name, is_ready=True)
    game_state.players.append(host_player)
    game_state.message = f"Game created! Share code: {game_id}"
    
    return game_state


def join_game(game_state: GameState, player_id: str, player_name: str) -> GameState:
    """Add a player to the game."""
    if game_state.phase != GamePhase.WAITING_FOR_PLAYERS:
        return game_state
    
    if len(game_state.players) >= 6:
        return game_state
    
    # Check if player already in game
    if game_state.get_player(player_id):
        return game_state
    
    new_player = Player(player_id=player_id, name=player_name)
    game_state.players.append(new_player)
    game_state.message = f"{player_name} joined the game! ({len(game_state.players)} players)"
    game_state.last_updated = datetime.now().isoformat()
    
    return game_state


def rejoin_game(game_state: GameState, player_id: str, player_name: str) -> tuple[GameState, bool]:
    """
    Allow a player to rejoin an in-progress game.
    Returns (game_state, success_flag).
    """
    # Check if player was already in the game by player_id
    existing_player = game_state.get_player(player_id)
    if existing_player:
        # Player is already in the game, just mark as connected
        existing_player.is_connected = True
        existing_player.name = player_name  # Update name in case it changed
        game_state.last_updated = datetime.now().isoformat()
        return game_state, True
    
    # Check if there's a player with same name (case insensitive) to take over
    # This allows rejoining even if the session changed (new browser, refresh, etc.)
    for player in game_state.players:
        if player.name.lower() == player_name.lower():
            old_player_id = player.player_id
            player.player_id = player_id  # Reassign to new session
            player.is_connected = True
            
            # If this player was the host, update host_id too
            if game_state.host_id == old_player_id:
                game_state.host_id = player_id
            
            game_state.message = f"🔄 {player_name} has reconnected!"
            game_state.last_updated = datetime.now().isoformat()
            return game_state, True
    
    return game_state, False


def leave_game(game_state: GameState, player_id: str) -> GameState:
    """
    Mark a player as disconnected/left the game.
    If the host leaves, pass host duties to another connected player.
    """
    player = game_state.get_player(player_id)
    if not player:
        return game_state
    
    player.is_connected = False
    
    # If this player was the host, transfer host to another connected player
    if game_state.host_id == player_id:
        connected_players = [p for p in game_state.players if p.is_connected and p.player_id != player_id]
        if connected_players:
            new_host = connected_players[0]
            game_state.host_id = new_host.player_id
            game_state.message = f"🚪 {player.name} has left! 👑 {new_host.name} is now the host!"
        else:
            game_state.message = f"🚪 {player.name} has left the game!"
    else:
        game_state.message = f"🚪 {player.name} has left the game!"
    
    game_state.last_updated = datetime.now().isoformat()
    
    return game_state


def send_chat_message(game_state: GameState, player_id: str, message: str) -> GameState:
    """
    Add a chat message to the game.
    """
    player = game_state.get_player(player_id)
    if not player or not message.strip():
        return game_state
    
    chat_msg = ChatMessage(
        player_name=player.name,
        message=message.strip()[:200],  # Limit message length
        timestamp=datetime.now().strftime("%H:%M")
    )
    
    # Keep last 50 messages max
    game_state.chat_messages.append(chat_msg)
    if len(game_state.chat_messages) > 50:
        game_state.chat_messages = game_state.chat_messages[-50:]
    
    game_state.last_updated = datetime.now().isoformat()
    
    return game_state


def start_game(game_state: GameState) -> GameState:
    """Start the game (called by host)."""
    if len(game_state.players) < 2:
        game_state.message = "Need at least 2 players to start!"
        return game_state
    
    # Deal first round
    game_state = deal_cards(game_state)
    game_state.phase = GamePhase.BIDDING
    game_state.message = f"Round 1 begins! {game_state.current_player.name}'s turn to bid."
    game_state.last_updated = datetime.now().isoformat()
    
    return game_state
