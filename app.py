import streamlit as st
import requests

st.set_page_config(page_title="Football AI", layout="centered", page_icon="⚽")

st.title("⚽ Football AI Betting App")

# 🔑 Use Streamlit Secrets for your API key in production!
API_KEY = st.secrets["API_KEY"]
bankroll = st.sidebar.number_input("Enter your bankroll (£)", value=1000, step=100)

def kelly(prob, odds):
    b = odds - 1
    q = 1 - prob
    # Standard Kelly formula
    f = (b * prob - q) / b
    # Fractional Kelly (0.25) to reduce volatility/risk of ruin
    return max(f, 0) * 0.25 

def predict(home, away):
    # TODO: This is where your ML model will eventually go
    return {"home_win": 0.45, "draw": 0.25, "away_win": 0.30}

def get_matches():
    if not API_KEY:
        st.warning("Please enter your API Key in the sidebar.")
        return []
    
    # Using 'uk' as a region often gives better coverage for EPL
    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={API_KEY}&regions=uk&markets=h2h&oddsFormat=decimal"
    
    try:
        res = requests.get(url)
        res.raise_for_status() # Check for 401 (invalid key) or 429 (out of credits)
        return res.json()
    except Exception as e:
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
            
