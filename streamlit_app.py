import streamlit as st
st.set_page_config(page_title="Insider-Terminal", layout="centered", initial_sidebar_state="collapsed")
import time
from PIL import Image, ImageFilter
import os
from supabase import create_client, Client

# --- Blurred Dashboard Background ---
def blurred_dashboard():
        st.markdown(
            """
            <style>
            .blur-bg {
                position: fixed;
                top: 0; left: 0; width: 100vw; height: 100vh;
                z-index: 0;
                filter: blur(12px) brightness(0.7);
                background: url('https://images.unsplash.com/photo-1691643158804-d3f02eb456a3?q=80&w=1074&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D') center/cover no-repeat;
            }
            </style>
            <div class="blur-bg"></div>
            """,
            unsafe_allow_html=True
        )

# --- Dark-Mode Login Modal (German) ---
def login_modal():
    st.markdown(
        """
        <div class="modal">
            <h3>SYSTEM-ALARM: INSTITUTIONELLE DATEN ERKANNT</h3>
            <p>Verbindung: <b>Sicher</b><br>
            Datenfeed: <b>Dark Pool & Gamma Exposure</b><br>
            Status: <b>GESPERRT</b></p>
            <p>Um Serverüberlastung und Bot-Scraping zu verhindern, ist der Zugang nur verifizierten menschlichen Tradern gestattet.</p>
            <form>
                <label>Name</label><input type="text" placeholder="Ihr Name" />
                <label>Telefonnummer (+49)</label><input type="tel" placeholder="+49..." />
                <label>Erfahrungslevel</label>
                <select>
                    <option>Anfänger</option>
                    <option>Profi</option>
                </select>
                <button type="submit">Verbinden</button>
            </form>
        </div>
        """,
        unsafe_allow_html=True
    )

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rnpzbzgeappnvtbbwlzh.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_secret_PG3bfhS-_4_a-emz9GHq7A_8EJMhLWB")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def main():

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        blurred_dashboard()
        # Main Headline and Sub-Headline
        st.markdown("""
            <h2 style='margin-bottom:0.5rem;'>SYSTEM-STATUS: GESPERRT (LEVEL 3)</h2>
            <p style='font-size:1.1rem;'>DATEN-FEED: DARK POOL LIQUIDITY & GAMMA EXPOSURE (XETRA/EUREX)</p>
        """, unsafe_allow_html=True)
        # Warning/Reason for Lock
        st.warning("""
            SICHERHEITSPROTOKOLL AKTIV\n\nAufgrund hoher Serverauslastung durch Hochfrequenz-Algorithmen ist der öffentliche Zugang zum Echtzeit-Terminal momentan limitiert.\nUm Bot-Scraping zu verhindern und die Latenz (Ping) unter 20ms zu halten, ist eine manuelle Authentifizierung erforderlich.
        """)
        # Streamlit form for login
        with st.form(key="login_form"):
            name = st.text_input("Name")
            phone = st.text_input("Telefonnummer (+49)")
            experience = st.selectbox("Erfahrungslevel", [
                "Retail (< 10k Portfolio)",
                "Pro Trader (> 50k Portfolio)",
                "Institutional / Quant"
            ])
            submit = st.form_submit_button("Verbinden")
            if submit:
                if name and phone.startswith("+49"):
                    # Save info to Supabase
                    try:
                        data = {
                            "name": name,
                            "phonenumber": phone,
                            "level": experience,
                        }
                        response = supabase.table("leads").insert(data).execute()
                        # Success if status_code is 200/201 or if data is present
                        if (hasattr(response, 'status_code') and response.status_code in [200, 201]) or (hasattr(response, 'data') and response.data):
                            st.success("Info erfolgreich gespeichert!")
                        else:
                            st.error("Fehler beim Speichern: " + str(response))
                    except Exception as e:
                        st.error(f"Fehler beim Speichern: {e}")
                    st.session_state['logged_in'] = True
                    st.session_state['name'] = name
                    st.rerun()
                else:
                    st.error("Bitte geben Sie einen Namen und eine gültige deutsche Telefonnummer (+49) ein.")
    else:
        # Main dashboard unlocked
        st.markdown("<style>.blur-bg{display:none !important;}</style>", unsafe_allow_html=True)
        st.title("Das Insider-Terminal: Retail Sentiment vs. Dark Pool Scanner")
        st.subheader("DAX 40 | Rheinmetall | NVIDIA | Gold")
        st.info("Zugang freigeschaltet. Willkommen, {}!".format(st.session_state.get('name', 'Trader')))
        st.markdown("---")
        st.header("1. Smart Money Divergenz")
        st.write("Hier sehen Sie die Divergenz zwischen Retail-Sentiment und Dark Pool Volumen.")
        import numpy as np
        import pandas as pd
        import altair as alt
        # Simulated data for DAX/NVIDIA
        dates = pd.date_range(end=pd.Timestamp.today(), periods=30)
        retail = np.random.normal(loc=100, scale=10, size=30).cumsum()
        dark_pool = retail + np.random.normal(loc=-20, scale=15, size=30)
        df = pd.DataFrame({
            'Datum': dates,
            'Retail-Sentiment': retail,
            'Dark Flow': dark_pool
        })
        base = alt.Chart(df).encode(x='Datum:T')
        retail_line = base.mark_line(color='green', strokeWidth=3).encode(y='Retail-Sentiment:Q', tooltip=['Datum', 'Retail-Sentiment'])
        dark_line = base.mark_line(color='red', strokeDash=[5,5], strokeWidth=3).encode(y='Dark Flow:Q', tooltip=['Datum', 'Dark Flow'])
        chart = retail_line + dark_line
        st.altair_chart(chart, use_container_width=True)
        # Signal logic
        cross = np.where((retail[:-1] < dark_pool[:-1]) & (retail[1:] >= dark_pool[1:]), True, False)
        if np.any(cross):
            st.markdown("<div style='background:#e50914;color:#fff;padding:1rem;border-radius:8px;text-align:center;font-size:1.5rem;'>SHORT SIGNAL!</div>", unsafe_allow_html=True)
        else:
            st.success("Kein Short-Signal aktuell.")
        st.header("2. Knock-Out Rechner")
        st.write("Berechnen Sie Ihr KO-Level und die Wahrscheinlichkeit, dass es heute erreicht wird.")
        ko_leverage = st.number_input("Ihr Hebel (z.B. 50)", min_value=1, max_value=500, value=50)
        # Simulate KO level and probability
        current_price = 16000  # Example DAX price
        ko_level = current_price - (current_price / ko_leverage)
        probability = min(99, 50 + ko_leverage // 2)  # Simple logic for demo
        st.write(f"Ihr KO-Level: {ko_level:.2f}")
        st.write(f"Wahrscheinlichkeit, dass Ihr KO heute erreicht wird: {probability}%")
        if probability > 80:
            st.warning("Empfehlung: Niedrigeren Hebel wählen!")
        st.markdown("<b>Lead Gen:</b> Um mit 500:1 Hebel ohne KO-Hunting zu traden, nutzen Sie <a href='#' style='color:#e50914;'>Ihren Affiliate Broker</a>.", unsafe_allow_html=True)
        col1, col2 = st.columns([2, 1])
        with col1:
            st.header("3. Rheinmetall War Room")
            st.write("News Sentiment AI für Rheinmetall (RHM) – Bullish/Bearish basierend auf deutschen Nachrichten.")
            # Simulate news sentiment
            news = [
                "Bundeswehr erhält neuen Vertrag mit Rheinmetall",
                "Rheinmetall liefert Panzer an die Ukraine",
                "Rheinmetall gewinnt Großauftrag",
                "Kritik an Verteidigungsbudget",
                "Rheinmetall Aktie fällt nach Gewinnwarnung"
            ]
            keywords_bull = ["Bundeswehr", "Vertrag", "Ukraine", "Großauftrag", "liefert", "gewinnt"]
            keywords_bear = ["Kritik", "fällt", "Gewinnwarnung"]
            bull_score = sum(any(k in n for k in keywords_bull) for n in news)
            bear_score = sum(any(k in n for k in keywords_bear) for n in news)
            sentiment = bull_score - bear_score
            if sentiment > 0:
                status = "Bullish"
                color = "#27ae60"
            elif sentiment < 0:
                status = "Bearish"
                color = "#e50914"
            else:
                status = "Neutral"
                color = "#f1c40f"
            st.markdown(f"<div style='width:100%;text-align:center;'><span style='font-size:2rem;font-weight:bold;color:{color};'>Sentiment: {status}</span></div>", unsafe_allow_html=True)
            st.progress(min(1.0, max(0.0, (bull_score/(bull_score+bear_score+1)))), text=f"Bullish: {bull_score} | Bearish: {bear_score}")
            st.write("Letzte Nachrichten:")
            for n in news:
                st.write(f"- {n}")
        with col2:
            st.header("Leverage Calculator")
            lev_price = st.number_input("Entry Price", min_value=0.0, value=16000.0)
            lev_leverage = st.number_input("Leverage", min_value=1, value=50)
            ko_level = lev_price - (lev_price / lev_leverage)
            st.write(f"KO Level: {ko_level:.2f}")
            st.header("Profit Calculator")
            profit_entry = st.number_input("Entry Price (Profit)", min_value=0.0, value=16000.0)
            profit_exit = st.number_input("Exit Price", min_value=0.0, value=16100.0)
            position_size = st.number_input("Position Size", min_value=0.0, value=1.0)
            profit = (profit_exit - profit_entry) * position_size
            st.write(f"Profit/Loss: {profit:.2f}")

if __name__ == "__main__":
    # Hide Streamlit default footer, main menu, and default page content
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stApp [data-testid='stAppViewContainer'] > .main > div:first-child {display: none !important;}
        </style>
    """, unsafe_allow_html=True)
    main()

    # ...existing code...
