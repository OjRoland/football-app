import streamlit as st
import requests
import sqlite3
import pandas as pd
from scipy.stats import poisson

# --- 🛠️ CONFIG & DATABASE ---
DB_NAME = "bets_tracker.db"

# Pulling keys directly from Secrets
API_KEY = st.secrets["ODDS_API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY, event TEXT, selection TEXT, odds REAL, stake REAL, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 🤖 AI PREDICTION ENGINE (Poisson Distribution) ---
def get_poisson_probs(home_avg, away_avg):
    """Calculates win/draw/loss probabilities."""
    max_goals = 8 
    home_probs = [poisson.pmf(i, home_avg) for i in range(max_goals)]
    away_probs = [poisson.pmf(i, away_avg) for i in range(max_goals)]
    
    p_home, p_draw, p_away = 0, 0, 0
    for h in range(max_goals):
        for a in range(max_goals):
            prob = home_probs[h] * away_probs[a]
            if h > a: p_home += prob
            elif h < a: p_away += prob
            else: p_draw += prob
    return {"home": p_home, "draw": p_draw, "away": p_away}

# --- 🚀 TELEGRAM ALERTS ---
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={message}"
    try:
        requests.get(url)
    except:
        st.error("Failed to send Telegram alert.")

# --- 📊 UI SETUP ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽")
st.title("🏆 Football AI: Value Betting Suite")

# Sidebar for global settings
bankroll = st.sidebar.number_input("Total Bankroll (£)", value=1000)
risk_factor = st.sidebar.slider("Kelly Fraction (Risk)", 0.01, 0.1, 0.05)

tabs = st.tabs(["🎯 Live Value Scraper", "📈 My Bet Tracker"])

# --- TAB 1: LIVE VALUE ---
with tabs[0]:
    leagues = {
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 EPL": "soccer_epl",
        "🇪🇸 La Liga": "soccer_spain_la_liga",
        "🇩🇪 Bundesliga": "soccer_germany_bundesliga",
        "🇮🇹 Serie A": "soccer_italy_serie_a",
        "🇫🇷 Ligue 1": "soccer_france_ligue_1"
    }
    
    selected_league = st.selectbox("Choose League", list(leagues.keys()))
    
    if st.button(f"Scan {selected_league} for Value"):
        url = f"https://api.the-odds-api.com/v4/sports/{leagues[selected_league]}/odds/?apiKey={API_KEY}&regions=uk&markets=h2h"
        
        try:
            res = requests.get(url)
            data = res.json()
            
            if not data:
                st.info("No upcoming matches found for this league.")
            
            for game in data:
                if not game.get("bookmakers"): continue
                
                home = game["home_team"]
                away = game["away_team"]
                
                # --- AI LOGIC ---
                # Placeholder: In a real AI, we'd fetch actual xG data.
                # Currently assumes a standard 1.7 vs 1.2 goal expectation.
                probs = get_poisson_probs(1.7, 1.2) 
                
                bookie = game["bookmakers"][0]
                odds_list = {o['name']: o['price'] for o in bookie['markets'][0]['outcomes']}
                
                h_odds = odds_list.get(home)
                edge = (probs['home'] * h_odds) - 1 if h_odds else 0

                if edge > 0.05: # Only show if > 5% Value
                    st.markdown(f"### {home} vs {away}")
                    st.write(f"**AI Win Prob:** {probs['home']:.1%} | **Bookie Odds:** {h_odds}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Bet {home}", key=f"bet_{home}"):
                            # Log to DB
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("INSERT INTO bets (event, selection, odds, stake, status) VALUES (?,?,?,?,?)",
                                         (f"{home} vs {away}", home, h_odds, bankroll * risk_factor, "PENDING"))
                            conn.commit()
                            # Send Alert
                            send_telegram(f"🎯 VALUE BET FOUND!\n{home} vs {away}\nSelection: {home}\nOdds: {h_odds}\nEdge: {edge:.2%}")
                            st.success("Bet Tracked & Telegram Sent!")
                    st.divider()
        except Exception as e:
            st.error(f"Error: {e}")

# --- TAB 2: TRACKER ---
with tabs[1]:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM bets", conn)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        if st.button("🗑️ Reset Tracker"):
            conn.execute("DELETE FROM bets")
            conn.commit()
            st.rerun()
    else:
        st.write("No bets tracked yet.")
        st.error(f"Error fetching data: {e}")
        return []

if st.button("Load & Analyze Matches"):
    matches = get_matches()
    
    if not matches:
        st.info("No matches found or API key is missing.")
    
    for game in matches:
        # 🛡️ Safety Check: Ensure bookmakers data exists
        if not game.get("bookmakers"):
            continue

        try:
            home = game["home_team"]
            away = game["away_team"]
            
            # Get the first available bookie and market
            market = game["bookmakers"][0]["markets"][0]
            outcomes = market["outcomes"] # List of 3 outcomes (Home, Away, Draw)

            # Map the outcomes by name to ensure we don't mix up Home/Away odds
            odds_dict = {o['name']: o['price'] for o in outcomes}
            home_odds = odds_dict.get(home)
            away_odds = odds_dict.get(away)

            if not home_odds or not away_odds:
                continue

            probs = predict(home, away)
            
            # Calculate Expected Value (EV)
            # EV = (Probability * Odds) - 1
            home_ev = (probs["home_win"] * home_odds) - 1
            away_ev = (probs["away_win"] * away_odds) - 1

            with st.expander(f"📊 {home} vs {away}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Model Probs:** H: {probs['home_win']:.2%} | A: {probs['away_win']:.2%}")
                    st.write(f"**Market Odds:** H: {home_odds} | A: {away_odds}")

                with col2:
                    if home_ev > 0:
                        stake = bankroll * kelly(probs["home_win"], home_odds)
                        st.success(f"🎯 VALUE HOME: Stake £{stake:.2f} (EV: {home_ev:+.2f})")
                    elif away_ev > 0:
                        stake = bankroll * kelly(probs["away_win"], away_odds)
                        st.success(f"🎯 VALUE AWAY: Stake £{stake:.2f} (EV: {away_ev:+.2f})")
                    else:
                        st.info("No value found.")

        except (KeyError, IndexError):
            continue
            
