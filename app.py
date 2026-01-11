"""
Wizard Card Game - Main Streamlit Application
A multiplayer turn-based card game with auto-refresh for real-time play.
"""

import streamlit as st
import uuid
import time
from datetime import datetime

from game_logic import (
    GameState, GamePhase, Player, Card, Suit,
    create_new_game, join_game, start_game, deal_cards,
    place_bid, play_card, get_valid_cards, start_next_trick, start_next_round
)
from database import get_database
import config


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize session state variables."""
    if 'player_id' not in st.session_state:
        st.session_state.player_id = str(uuid.uuid4())[:8]
    if 'player_name' not in st.session_state:
        st.session_state.player_name = ""
    if 'game_id' not in st.session_state:
        st.session_state.game_id = None
    if 'last_known_update' not in st.session_state:
        st.session_state.last_known_update = None
    if 'db' not in st.session_state:
        st.session_state.db = get_database()


# =============================================================================
# AUTO-REFRESH MECHANISM
# =============================================================================

def check_for_updates():
    """Check if game state has been updated by another player."""
    if not st.session_state.game_id:
        return False
    
    current_update = st.session_state.db.get_last_updated(st.session_state.game_id)
    
    if current_update and current_update != st.session_state.last_known_update:
        st.session_state.last_known_update = current_update
        return True
    return False


def setup_auto_refresh():
    """Setup auto-refresh for waiting players."""
    game_state = load_game_state()
    if not game_state:
        return
    
    # Only auto-refresh if it's not our turn
    current_player = game_state.current_player
    is_my_turn = current_player and current_player.player_id == st.session_state.player_id
    
    # Auto-refresh when waiting for other players
    if game_state.phase != GamePhase.GAME_OVER and not is_my_turn:
        time.sleep(0.1)  # Small delay to prevent rapid refreshes
        st.rerun()


# =============================================================================
# DATABASE HELPERS
# =============================================================================

def load_game_state() -> GameState:
    """Load the current game state from database."""
    if not st.session_state.game_id:
        return None
    return st.session_state.db.load_game(st.session_state.game_id)


def save_game_state(game_state: GameState):
    """Save game state to database."""
    st.session_state.db.save_game(game_state)
    st.session_state.last_known_update = game_state.last_updated


# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_lobby():
    """Render the game lobby (create/join game)."""
    st.title("🧙 Wizard Card Game")
    st.markdown("---")
    
    # Player name input
    if not st.session_state.player_name:
        st.subheader("👤 Enter Your Name")
        name = st.text_input("Your name:", max_chars=20, key="name_input")
        if st.button("Set Name", type="primary"):
            if name.strip():
                st.session_state.player_name = name.strip()
                st.rerun()
            else:
                st.error("Please enter a valid name!")
        return
    
    st.success(f"Welcome, **{st.session_state.player_name}**!")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎮 Create New Game")
        if st.button("Create Game", type="primary", use_container_width=True):
            game_id = str(uuid.uuid4())[:6].upper()
            game_state = create_new_game(
                game_id=game_id,
                host_id=st.session_state.player_id,
                host_name=st.session_state.player_name
            )
            save_game_state(game_state)
            st.session_state.game_id = game_id
            st.rerun()
    
    with col2:
        st.subheader("🔗 Join Existing Game")
        game_code = st.text_input("Enter Game Code:", max_chars=6, key="join_code")
        if st.button("Join Game", use_container_width=True):
            game_code = game_code.upper().strip()
            if game_code:
                game_state = st.session_state.db.load_game(game_code)
                if game_state:
                    if game_state.phase != GamePhase.WAITING_FOR_PLAYERS:
                        st.error("Game has already started!")
                    elif len(game_state.players) >= 6:
                        st.error("Game is full!")
                    else:
                        game_state = join_game(game_state, st.session_state.player_id, st.session_state.player_name)
                        save_game_state(game_state)
                        st.session_state.game_id = game_code
                        st.rerun()
                else:
                    st.error("Game not found!")
    
    # Show available games (for local testing)
    st.markdown("---")
    with st.expander("🔍 Available Games (Debug)"):
        games = st.session_state.db.list_games()
        if games:
            for gid in games:
                gs = st.session_state.db.load_game(gid)
                if gs:
                    st.write(f"**{gid}** - {len(gs.players)} players - {gs.phase.value}")
        else:
            st.write("No active games")


def render_waiting_room(game_state: GameState):
    """Render the waiting room before game starts."""
    st.title("🧙 Wizard - Waiting Room")
    
    # Game code display
    st.info(f"📋 **Game Code: {game_state.game_id}** - Share this with friends!")
    
    st.markdown("---")
    
    # Player list
    st.subheader(f"👥 Players ({len(game_state.players)}/6)")
    
    for i, player in enumerate(game_state.players):
        icon = "👑" if player.player_id == game_state.host_id else "👤"
        you = " (You)" if player.player_id == st.session_state.player_id else ""
        st.write(f"{icon} {player.name}{you}")
    
    st.markdown("---")
    
    # Host controls
    if st.session_state.player_id == game_state.host_id:
        if len(game_state.players) >= 2:
            if st.button("🚀 Start Game", type="primary", use_container_width=True):
                game_state = start_game(game_state)
                save_game_state(game_state)
                st.rerun()
        else:
            st.warning("Need at least 2 players to start!")
    else:
        st.info("⏳ Waiting for host to start the game...")
    
    # Leave game button
    if st.button("🚪 Leave Game"):
        st.session_state.game_id = None
        st.rerun()
    
    # Auto-refresh for waiting players
    with st.spinner("Waiting for players..."):
        time.sleep(config.REFRESH_INTERVAL)
        st.rerun()


def render_card(card: Card, selectable: bool = False, key: str = None) -> bool:
    """Render a single card and return if clicked."""
    # Card colors based on suit
    colors = {
        Suit.HEARTS: "#ff6b6b",
        Suit.DIAMONDS: "#ff6b6b", 
        Suit.CLUBS: "#333333",
        Suit.SPADES: "#333333",
        Suit.WIZARD: "#9b59b6",
        Suit.JESTER: "#27ae60"
    }
    
    bg_color = colors.get(card.suit, "#ffffff")
    text_color = "#ffffff" if card.suit in [Suit.CLUBS, Suit.SPADES, Suit.WIZARD, Suit.JESTER] else "#000000"
    
    card_html = f"""
    <div style="
        background: {bg_color};
        color: {text_color};
        border: 2px solid #333;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
        font-size: 18px;
        font-weight: bold;
        min-width: 60px;
        margin: 2px;
        display: inline-block;
    ">
        {card.display_name}
    </div>
    """
    
    if selectable and key:
        return st.button(card.display_name, key=key, use_container_width=True)
    else:
        st.markdown(card_html, unsafe_allow_html=True)
        return False


def render_game_info(game_state: GameState):
    """Render game information sidebar."""
    st.sidebar.title("📊 Game Info")
    st.sidebar.markdown(f"**Round:** {game_state.current_round} / {game_state.max_rounds}")
    st.sidebar.markdown(f"**Trick:** {game_state.current_trick} / {game_state.cards_this_round}")
    
    if game_state.trump_suit:
        st.sidebar.markdown(f"**Trump:** {game_state.trump_suit.value}")
    elif game_state.trump_card:
        st.sidebar.markdown("**Trump:** None (Jester)")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏆 Scores")
    
    # Sort players by score
    sorted_players = sorted(game_state.players, key=lambda p: p.score, reverse=True)
    for player in sorted_players:
        you = " 👈" if player.player_id == st.session_state.player_id else ""
        bid_info = f" (Bid: {player.bid}, Won: {player.tricks_won})" if player.bid is not None else ""
        st.sidebar.write(f"**{player.name}:** {player.score} pts{bid_info}{you}")


def render_bidding_phase(game_state: GameState, my_player: Player):
    """Render the bidding phase UI."""
    st.title("🧙 Wizard - Bidding Phase")
    render_game_info(game_state)
    
    st.markdown(f"### Round {game_state.current_round}")
    
    # Show trump
    if game_state.trump_card:
        st.write(f"**Trump Card:** {game_state.trump_card.display_name}")
        if game_state.trump_suit:
            st.write(f"**Trump Suit:** {game_state.trump_suit.value}")
        else:
            st.write("**No trump this round!**")
    
    st.markdown("---")
    
    # Show current bids
    st.subheader("📝 Bids")
    cols = st.columns(len(game_state.players))
    for i, player in enumerate(game_state.players):
        with cols[i]:
            you = " (You)" if player.player_id == st.session_state.player_id else ""
            if player.bid is not None:
                st.success(f"{player.name}{you}: **{player.bid}**")
            else:
                st.warning(f"{player.name}{you}: ?")
    
    st.markdown("---")
    
    # Show my hand
    st.subheader("🃏 Your Hand")
    hand_cols = st.columns(len(my_player.hand))
    for i, card in enumerate(my_player.hand):
        with hand_cols[i]:
            render_card(card)
    
    st.markdown("---")
    
    # Bidding interface
    is_my_turn = game_state.current_player.player_id == st.session_state.player_id
    
    if is_my_turn:
        st.success("🎯 **Your turn to bid!**")
        max_bid = game_state.cards_this_round
        bid = st.selectbox("Select your bid:", options=list(range(max_bid + 1)), key="bid_select")
        
        if st.button("Submit Bid", type="primary"):
            game_state = place_bid(game_state, st.session_state.player_id, bid)
            save_game_state(game_state)
            st.rerun()
    else:
        st.info(f"⏳ Waiting for **{game_state.current_player.name}** to bid...")
        time.sleep(config.REFRESH_INTERVAL)
        st.rerun()


def render_playing_phase(game_state: GameState, my_player: Player):
    """Render the card playing phase UI."""
    st.title("🧙 Wizard - Playing Phase")
    render_game_info(game_state)
    
    st.markdown(f"### Round {game_state.current_round} - Trick {game_state.current_trick}")
    
    # Show lead suit if set
    if game_state.lead_suit:
        st.write(f"**Lead Suit:** {game_state.lead_suit.value}")
    
    st.markdown("---")
    
    # Show cards played this trick
    st.subheader("🎴 Cards Played")
    if game_state.current_trick_cards:
        trick_cols = st.columns(len(game_state.players))
        played_ids = {pc.player_id for pc in game_state.current_trick_cards}
        
        for i, player in enumerate(game_state.players):
            with trick_cols[i]:
                st.write(f"**{player.name}**")
                played_card = next((pc.card for pc in game_state.current_trick_cards if pc.player_id == player.player_id), None)
                if played_card:
                    render_card(played_card)
                else:
                    st.write("...")
    else:
        st.write("No cards played yet")
    
    st.markdown("---")
    
    # Show my hand
    st.subheader("🃏 Your Hand")
    is_my_turn = game_state.current_player.player_id == st.session_state.player_id
    
    if is_my_turn:
        st.success("🎯 **Your turn to play!**")
        valid_cards = get_valid_cards(my_player, game_state.lead_suit)
        
        hand_cols = st.columns(len(my_player.hand))
        for i, card in enumerate(my_player.hand):
            with hand_cols[i]:
                is_valid = card in valid_cards
                btn_type = "primary" if is_valid else "secondary"
                disabled = not is_valid
                
                if st.button(card.display_name, key=f"card_{i}", type=btn_type, disabled=disabled, use_container_width=True):
                    game_state = play_card(game_state, st.session_state.player_id, card)
                    save_game_state(game_state)
                    st.rerun()
        
        if len(valid_cards) < len(my_player.hand):
            st.caption("Grayed out cards cannot be played (must follow suit)")
    else:
        hand_cols = st.columns(len(my_player.hand))
        for i, card in enumerate(my_player.hand):
            with hand_cols[i]:
                render_card(card)
        
        st.info(f"⏳ Waiting for **{game_state.current_player.name}** to play...")
        time.sleep(config.REFRESH_INTERVAL)
        st.rerun()


def render_trick_complete(game_state: GameState, my_player: Player):
    """Render the trick complete screen."""
    st.title("🧙 Wizard - Trick Complete!")
    render_game_info(game_state)
    
    # Show winning card
    winner = game_state.get_player(game_state.trick_winner)
    st.success(f"🏆 **{winner.name}** wins the trick!")
    
    # Show all cards played
    st.subheader("🎴 Cards Played")
    trick_cols = st.columns(len(game_state.current_trick_cards))
    for i, played in enumerate(game_state.current_trick_cards):
        player = game_state.get_player(played.player_id)
        with trick_cols[i]:
            is_winner = played.player_id == game_state.trick_winner
            if is_winner:
                st.markdown("**👑 WINNER**")
            st.write(f"**{player.name}**")
            render_card(played.card)
    
    st.markdown("---")
    
    # Continue button (anyone can click to proceed)
    if st.button("Continue to Next Trick", type="primary"):
        game_state = start_next_trick(game_state)
        save_game_state(game_state)
        st.rerun()
    
    # Auto-continue after delay
    time.sleep(config.REFRESH_INTERVAL)
    st.rerun()


def render_round_complete(game_state: GameState, my_player: Player):
    """Render the round complete screen."""
    st.title("🧙 Wizard - Round Complete!")
    render_game_info(game_state)
    
    st.success(f"Round {game_state.current_round} is complete!")
    
    # Show round results
    st.subheader("📊 Round Results")
    
    for player in game_state.players:
        made_bid = player.bid == player.tricks_won
        emoji = "✅" if made_bid else "❌"
        points = 20 + (10 * player.tricks_won) if made_bid else -10 * abs(player.bid - player.tricks_won)
        sign = "+" if points >= 0 else ""
        
        you = " (You)" if player.player_id == st.session_state.player_id else ""
        st.write(f"{emoji} **{player.name}{you}**: Bid {player.bid}, Won {player.tricks_won} → {sign}{points} points")
    
    st.markdown("---")
    
    # Continue button
    is_host = st.session_state.player_id == game_state.host_id
    
    if is_host:
        if st.button("Start Next Round", type="primary"):
            game_state = start_next_round(game_state)
            save_game_state(game_state)
            st.rerun()
    else:
        st.info("⏳ Waiting for host to start next round...")
        time.sleep(config.REFRESH_INTERVAL)
        st.rerun()


def render_game_over(game_state: GameState, my_player: Player):
    """Render the game over screen."""
    st.title("🧙 Wizard - Game Over!")
    
    # Find winner
    winner = max(game_state.players, key=lambda p: p.score)
    
    st.balloons()
    st.success(f"🏆 **{winner.name}** wins with **{winner.score}** points!")
    
    st.markdown("---")
    
    # Final standings
    st.subheader("🏅 Final Standings")
    sorted_players = sorted(game_state.players, key=lambda p: p.score, reverse=True)
    
    medals = ["🥇", "🥈", "🥉"]
    for i, player in enumerate(sorted_players):
        medal = medals[i] if i < 3 else f"{i+1}."
        you = " (You)" if player.player_id == st.session_state.player_id else ""
        st.write(f"{medal} **{player.name}{you}**: {player.score} points")
    
    st.markdown("---")
    
    # Play again
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Play Again", type="primary", use_container_width=True):
            # Create new game with same players
            if st.session_state.player_id == game_state.host_id:
                game_id = str(uuid.uuid4())[:6].upper()
                new_game = create_new_game(game_id, game_state.host_id, 
                                          game_state.get_player(game_state.host_id).name)
                save_game_state(new_game)
                st.session_state.game_id = game_id
            st.rerun()
    
    with col2:
        if st.button("🏠 Return to Lobby", use_container_width=True):
            st.session_state.game_id = None
            st.rerun()


def render_game(game_state: GameState):
    """Render the appropriate game screen based on phase."""
    my_player = game_state.get_player(st.session_state.player_id)
    
    if not my_player:
        st.error("You are not in this game!")
        st.session_state.game_id = None
        st.rerun()
        return
    
    if game_state.phase == GamePhase.WAITING_FOR_PLAYERS:
        render_waiting_room(game_state)
    elif game_state.phase == GamePhase.BIDDING:
        render_bidding_phase(game_state, my_player)
    elif game_state.phase == GamePhase.PLAYING:
        render_playing_phase(game_state, my_player)
    elif game_state.phase == GamePhase.TRICK_COMPLETE:
        render_trick_complete(game_state, my_player)
    elif game_state.phase == GamePhase.ROUND_COMPLETE:
        render_round_complete(game_state, my_player)
    elif game_state.phase == GamePhase.GAME_OVER:
        render_game_over(game_state, my_player)


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main():
    """Main application entry point."""
    st.set_page_config(
        page_title="Wizard Card Game",
        page_icon="🧙",
        layout="wide"
    )
    
    # Load custom CSS
    try:
        with open("styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass
    
    # Initialize session state
    init_session_state()
    
    # Check if in a game
    if st.session_state.game_id:
        game_state = load_game_state()
        if game_state:
            render_game(game_state)
        else:
            st.error("Game not found!")
            st.session_state.game_id = None
            st.rerun()
    else:
        render_lobby()


if __name__ == "__main__":
    main()
