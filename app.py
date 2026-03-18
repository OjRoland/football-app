import streamlit as st
import requests
import sqlite3
import pandas as pd
from scipy.stats import poisson

# --- CONFIG & DATABASE ---
DB_NAME = "bets_tracker.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY, event TEXT, selection TEXT, odds REAL, stake REAL, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 🤖 REAL AI PREDICTION (Poisson Model) ---
def get_poisson_probs(home_avg, away_avg):
    """Calculates win/draw/loss probabilities based on average goals."""
    # Simplified: In a real app, you'd fetch these averages from a sports data API
    # Here, we simulate 'strength' (e.g., Man City = 2.5, Leicester = 0.8)
    max_goals = 10
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
    token = st.secrets.get("TELEGRAM_TOKEN")
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}"
        requests.get(url)

# --- 📊 UI SETUP ---
st.set_page_config(page_title="Pro Football AI", layout="wide")
st.title("🏆 Pro AI Betting Suite")

tabs = st.tabs(["🎯 Live Value", "📈 Bet Tracker", "⚙️ Settings"])

# --- TAB 1: LIVE VALUE ---
with tabs[0]:
    API_KEY = st.sidebar.text_input("Odds API Key", type="password")
    leagues = {
        "EPL": "soccer_epl",
        "La Liga": "soccer_spain_la_liga",
        "Bundesliga": "soccer_germany_bundesliga",
        "Serie A": "soccer_italy_serie_a",
        "Ligue 1": "soccer_france_ligue_1"
    }
    
    selected_league = st.selectbox("Select League", list(leagues.keys()))
    
    if st.button("Find Value Bets"):
        url = f"https://api.the-odds-api.com/v4/sports/{leagues[selected_league]}/odds/?apiKey={API_KEY}&regions=uk&markets=h2h"
        data = requests.get(url).json()
        
        for game in data:
            home = game["home_team"]
            away = game["away_team"]
            
            # --- REAL AI LOGIC ---
            # NOTE: In a finished app, fetch real season averages here!
            # For now, we use 1.5 as a neutral baseline.
            probs = get_poisson_probs(1.7, 1.2) 
            
            try:
                bookie = game["bookmakers"][0]
                odds = {o['name']: o['price'] for o in bookie['markets'][0]['outcomes']}
                
                home_odds = odds[home]
                edge = (probs['home'] * home_odds) - 1
                
                if edge > 0.05: # 5% minimum edge
                    msg = f"🔥 VALUE FOUND: {home} to beat {away} at {home_odds}"
                    st.success(msg)
                    if st.button(f"Track Bet: {home}", key=home):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO bets (event, selection, odds, stake, status) VALUES (?,?,?,?,?)",
                                     (f"{home} vs {away}", home, home_odds, 10.0, "PENDING"))
                        conn.commit()
                        send_telegram(msg)
            except: continue

# --- TAB 2: TRACKER ---
with tabs[1]:
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM bets", conn)
    st.dataframe(df, use_container_width=True)
    if st.button("Clear History"):
        conn.execute("DELETE FROM bets")
        conn.commit()
        st.rerun()
        
