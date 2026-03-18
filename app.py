import streamlit as st
import requests

st.set_page_config(page_title="Football AI", layout="centered")

st.title("⚽ Football AI Betting App")

# 🔑 Your API Key (we’ll replace this later with secrets)
API_KEY = "PASTE_YOUR_ODDS_API_KEY_HERE"

# 💰 Bankroll input
bankroll = st.number_input("Enter your bankroll (£)", value=1000)

# 📊 Kelly formula
def kelly(prob, odds):
    b = odds - 1
    q = 1 - prob
    f = (b * prob - q) / b
    return max(f, 0) * 0.25  # 25% safer Kelly

# 🤖 Fake prediction (we’ll improve later)
def predict(home, away):
    return {
        "home_win": 0.45,
        "draw": 0.25,
        "away_win": 0.30
    }

# 🌍 Fetch EPL odds (you can expand later)
def get_matches():
    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={API_KEY}&regions=eu&markets=h2h"
    res = requests.get(url)
    return res.json()

# ▶️ Button
if st.button("Load Matches"):

    matches = get_matches()

    for game in matches:

        try:
            home = game["home_team"]
            away = game["away_team"]

            odds = game["bookmakers"][0]["markets"][0]["outcomes"]

            home_odds = odds[0]["price"]
            away_odds = odds[1]["price"]

            probs = predict(home, away)

            home_edge = probs["home_win"] * home_odds - 1
            away_edge = probs["away_win"] * away_odds - 1

            st.markdown(f"## {home} vs {away}")

            st.write("Home Win %:", probs["home_win"])
            st.write("Draw %:", probs["draw"])
            st.write("Away Win %:", probs["away_win"])

            if home_edge > 0:
                stake = bankroll * kelly(probs["home_win"], home_odds)
                st.success(f"VALUE BET: HOME | Stake £{stake:.2f}")

            if away_edge > 0:
                stake = bankroll * kelly(probs["away_win"], away_odds)
                st.success(f"VALUE BET: AWAY | Stake £{stake:.2f}")

            st.divider()

        except:
            continue
