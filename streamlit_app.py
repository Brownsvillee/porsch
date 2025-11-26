import streamlit as st
st.set_page_config(page_title="Positions & Liquidations Monitor", layout="wide", initial_sidebar_state="collapsed")
import os
import time
import pandas as pd
import numpy as np
import altair as alt

# Optional Supabase client — import only if available
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except Exception:
    SUPABASE_AVAILABLE = False

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
if SUPABASE_AVAILABLE and SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        supabase = None
else:
    supabase = None

# --- Styles: fixed header ---
CSS = """
<style>
.header { position: fixed; top: 0; left: 0; right: 0; z-index: 9999; background: #06101a; color: #fff; padding: 10px 18px; display:flex; align-items:center; gap:12px;}
.content { margin-top: 72px; padding: 12px 18px 40px 18px; }
.small-muted { color: rgba(255,255,255,0.6); font-size:0.9rem }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

def normalize_df(df):
    # Ensure expected columns exist, try to coerce common names
    df = df.copy()
    cols = [c.lower() for c in df.columns]
    mapping = {}
    for c in df.columns:
        lc = c.lower()
        if lc in ('pair','symbol','instrument'):
            mapping[c] = 'pair'
        if lc in ('address','wallet','addr'):
            mapping[c] = 'address'
        if lc in ('side',):
            mapping[c] = 'side'
        if lc in ('entry','entry_price'):
            mapping[c] = 'entry'
        if lc in ('liquidation','liq','liq_price'):
            mapping[c] = 'liq'
        if lc in ('current','mark','price'):
            mapping[c] = 'current'
        if lc in ('distance','distance_pct','dist'):
            mapping[c] = 'distance_pct'
        if lc in ('leverage',):
            mapping[c] = 'leverage'
        if lc in ('size','position_size','qty'):
            mapping[c] = 'size'
    df = df.rename(columns=mapping)
    expected = ['pair','address','side','entry','liq','current','distance_pct','leverage','size']
    for c in expected:
        if c not in df.columns:
            df[c] = np.nan
    # coerce numeric
    for c in ['entry','liq','current','distance_pct','leverage','size']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['side'] = df['side'].astype(str).str.upper().replace({'LONG':'LONG','SHORT':'SHORT'})
    return df[expected]

def generate_real_market_data(seed=42):
    """Generate realistic positions data for top 10 stocks, cryptos, and forex pairs."""
    np.random.seed(seed)
    
    # Top 10 stocks, cryptos, forex pairs
    stocks = [('AAPL', 230), ('MSFT', 440), ('GOOGL', 195), ('NVDA', 142), ('TSLA', 318),
              ('AMZN', 210), ('META', 580), ('BRKA', 640), ('JPMC', 225), ('KO', 72)]
    cryptos = [('BTC-USD', 60000), ('ETH-USD', 4000), ('XRP-USD', 3.2), ('SOL-USD', 245),
               ('ADA-USD', 1.12), ('DOGE-USD', 0.42), ('MATIC-USD', 0.98), ('LTC-USD', 145),
               ('BNB-USD', 685), ('AVAX-USD', 42)]
    forex = [('EUR-USD', 1.09), ('GBP-USD', 1.28), ('JPY-USD', 0.0067), ('CHF-USD', 1.18),
             ('CAD-USD', 0.72), ('AUD-USD', 0.65), ('NZD-USD', 0.59), ('SGD-USD', 0.75),
             ('HKD-USD', 0.128), ('SEK-USD', 0.095)]
    
    all_pairs = [('STOCK', s[0], s[1]) for s in stocks] + \
                [('CRYPTO', c[0], c[1]) for c in cryptos] + \
                [('FOREX', f[0], f[1]) for f in forex]
    
    rows = []
    for asset_type, pair_name, price in all_pairs:
        n_positions = np.random.randint(8, 25)
        for i in range(n_positions):
            side = np.random.choice(['LONG', 'SHORT'], p=[0.6, 0.4])
            entry = price * (1 + np.random.normal(0, 0.025))
            leverage = int(np.random.choice([2, 5, 10, 20, 50, 75], p=[0.15, 0.25, 0.25, 0.2, 0.1, 0.05]))
            
            if side == 'LONG':
                liq = entry - (entry / leverage) * (0.85 + np.random.rand() * 0.7)
            else:
                liq = entry + (entry / leverage) * (0.85 + np.random.rand() * 0.7)
            
            current = entry * (1 + np.random.normal(0, 0.02))
            distance_pct = (liq - current) / current * 100 if side == 'LONG' else (current - liq) / current * 100
            
            rows.append({
                'pair': pair_name,
                'asset_class': asset_type,
                'address': f'0x{np.random.randint(10**7):x}',
                'side': side,
                'entry': round(entry, 4),
                'liq': round(liq, 4),
                'current': round(current, 4),
                'distance_pct': round(distance_pct, 2),
                'leverage': leverage,
                'size': round(abs(np.random.normal(0.5, 2.0)) * 10, 4)
            })
    
    return pd.DataFrame(rows)

# Asset classes for filtering
ASSET_CLASSES = ['All', 'STOCK', 'CRYPTO', 'FOREX']

# Header
st.markdown(f"""
<div class="header">
  <div style='font-weight:700;font-size:1.05rem'>Positions & Liquidations Monitor</div>
  <div class='small-muted'> · View positions closest to liquidation · English UI</div>
  <div style='flex:1'></div>
  <div class='small-muted'>Repo: porsch</div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="content"></div>', unsafe_allow_html=True)

# New flow: require lead + CSV upload before unlocking the dashboard
container = st.container()
if 'unlocked' not in st.session_state:
    st.session_state['unlocked'] = False

with container:
    st.markdown('<div class="content"></div>', unsafe_allow_html=True)
    if not st.session_state['unlocked']:
        left, right = st.columns([3, 1])
        with left:
            st.subheader('Create Account')
            st.write('Register to access the Positions & Liquidations Monitor')
            
            with st.form('registration_form'):
                reg_name = st.text_input('Full name', placeholder='John Doe')
                reg_email = st.text_input('Email', placeholder='john@example.com')
                reg_phone = st.text_input('Phone (international format)', placeholder='+1234567890')
                reg_experience = st.selectbox('Experience level', ['Retail (< $10k)', 'Pro Trader (> $50k)', 'Institutional / Quant'])
                
                submit = st.form_submit_button('Create Account')
                
                if submit:
                    # Validate fields
                    if not reg_name or not reg_email or not reg_phone:
                        st.error('Please provide all fields: name, email, and phone.')
                    elif '@' not in reg_email:
                        st.error('Please provide a valid email address.')
                    else:
                        # Save to Supabase
                        if supabase is not None:
                            try:
                                payload = {
                                    'name': reg_name,
                                    'email': reg_email,
                                    'phone': reg_phone,
                                    'experience': reg_experience,
                                    'created_at': pd.Timestamp.now().isoformat()
                                }
                                result = supabase.table('leads').insert(payload).execute()
                                st.success('✅ Account created successfully! Unlocking dashboard...')
                                st.session_state['user'] = payload
                                st.session_state['unlocked'] = True
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f'Error creating account: {str(e)[:100]}')
                        else:
                            st.error('Supabase is not configured. Please check your environment variables.')
        
        with right:
            st.subheader('Features')
            st.write('''
            ✨ **Dashboard Includes:**
            - Top 10 stocks
            - Top 10 cryptocurrencies
            - Top 10 forex pairs
            - Real-time liquidation levels
            - Distance-to-liquidation tracking
            - Position filtering & analysis
            ''')

    else:
        # Dashboard (unlocked) — load real market data
        if 'market_data' not in st.session_state:
            st.session_state['market_data'] = generate_real_market_data()
        
        df = st.session_state['market_data']
        user_info = st.session_state.get('user', {})
        
        # Top header with user info
        st.markdown(f"Welcome, **{user_info.get('name', 'User')}**! 📊", unsafe_allow_html=True)
        
        left, right = st.columns([3, 1])
        with left:
            st.subheader('Filters')
            c1, c2, c3 = st.columns(3)
            with c1:
                asset_class = st.selectbox('Asset Class', ASSET_CLASSES)
            with c2:
                side = st.selectbox('Side', ['All', 'LONG', 'SHORT'])
            with c3:
                max_dist = st.slider('Max distance (%)', 0.0, 100.0, 20.0)
            
            # Apply filters
            df_view = df.copy()
            if asset_class != 'All':
                df_view = df_view[df_view['asset_class'] == asset_class]
            if side != 'All':
                df_view = df_view[df_view['side'] == side]
            df_view = df_view[df_view['distance_pct'].abs() <= max_dist]
            df_view['abs_distance'] = df_view['distance_pct'].abs()
            df_view = df_view.sort_values('abs_distance')
            
            st.markdown(f'### Positions — {len(df_view)} rows')
            if df_view.empty:
                st.info('No positions match filters.')
            else:
                display_cols = ['pair', 'asset_class', 'address', 'side', 'entry', 'current', 'liq', 'distance_pct', 'leverage', 'size']
                st.dataframe(
                    df_view[display_cols].reset_index(drop=True).style.format({
                        'entry': '{:.4f}', 'current': '{:.4f}', 'liq': '{:.4f}', 'distance_pct': '{:.2f}', 'size': '{:.4f}'
                    }), height=520
                )
                
                # Chart
                chart = alt.Chart(df_view.reset_index()).mark_bar().encode(
                    x=alt.X('distance_pct:Q', title='Distance to Liquidation (%)'),
                    y=alt.Y('pair:N', sort='-x', title='Pair'),
                    color=alt.Color('side:N', scale=alt.Scale(domain=['LONG', 'SHORT'], range=['#27ae60', '#e50914'])),
                    tooltip=['pair', 'asset_class', 'side', 'entry', 'current', 'liq', 'distance_pct', 'leverage']
                ).properties(height=420)
                st.altair_chart(chart, width=700)
        
        with right:
            st.subheader('Top Liquidations')
            if not df_view.empty:
                top = df_view.nsmallest(10, 'abs_distance')
                st.table(top[['pair', 'asset_class', 'side', 'current', 'liq', 'distance_pct', 'leverage']].reset_index(drop=True).style.format({
                    'current': '{:.4f}', 'liq': '{:.4f}', 'distance_pct': '{:.2f}'
                }))
            else:
                st.write('—')
            
            st.markdown('**Counts**')
            counts = df_view['side'].value_counts().reindex(['LONG', 'SHORT']).fillna(0).astype(int)
            st.write(counts.to_frame('count'))
            
            if st.button('Copy top addresses'):
                if not df_view.empty:
                    st.code('\n'.join(df_view['address'].head(50).tolist()))
                    st.success('Addresses shown — copy manually.')


if __name__ == '__main__':
    pass
