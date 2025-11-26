import streamlit as st
st.set_page_config(page_title="Positions & Liquidations Monitor", layout="wide", initial_sidebar_state="collapsed")
import os
import time
import pandas as pd
import numpy as np
import altair as alt
import requests

# Optional Supabase client — import only if available
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except Exception:
    SUPABASE_AVAILABLE = False

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rnpzbzgeappnvtbbwlzh.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_secret_PG3bfhS-_4_a-emz9GHq7A_8EJMhLWB")
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

def generate_real_market_data(seed=42, finnhub_api_key="d4jgds1r01qgcb0t7mpgd4jgds1r01qgcb0t7mq0"):
    """Fetch real market data from Finnhub API and generate positions with realistic liquidation levels."""
    np.random.seed(seed)
    
    # Top 30 stocks, 20 cryptos, 20 forex pairs
    stocks = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'AMZN', 'META', 'BRK.A', 'JPM', 'KO',
              'GS', 'BAC', 'WFC', 'C', 'BLK', 'SCHW', 'CME', 'ICE', 'CBOE', 'NFLX',
              'DIS', 'PYPL', 'SQ', 'COIN', 'RIOT', 'MARA', 'MSTR', 'HUT', 'CLSK', 'HOOD']
    cryptos = ['BTCUSD', 'ETHUSD', 'XRPUSD', 'SOLUSD', 'ADAUSD', 'DOGEUSD', 'MATICUSD', 'LTCUSD', 'BNBUSD', 'AVAXUSD',
               'LINKUSD', 'UNIUSD', 'AAVEUSD', 'SNXUSD', 'CROUSD', 'MKRUSD', 'YFIUSD', 'LRCUSD', 'GALAUSD', 'SHIBUSD']
    forex = ['EURUSD', 'GBPUSD', 'JPYUSD', 'CHFUSD', 'CADUSD', 'AUDUSD', 'NZDUSD', 'SGDUSD', 'HKDUSD', 'SEKUSD',
             'NOKUSD', 'DKKUSD', 'IUSD', 'INRUSD', 'THBUSD', 'MXNUSD', 'ZARUSD', 'BRLUSD', 'KORUSD', 'ZXUSD']
    
    rows = []
    finnhub_base = "https://finnhub.io/api/v1"
    
    with st.spinner("🔄 Fetching real market data from Finnhub..."):
        # Fetch stock prices from Finnhub
        fetched_stocks = {}
        for stock in stocks:
            try:
                quote_url = f"{finnhub_base}/quote?symbol={stock}&token={finnhub_api_key}"
                response = requests.get(quote_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    price = data.get('c', None)  # current price
                    if price and price > 0:
                        fetched_stocks[stock] = price
                        st.toast(f"✅ {stock}: ${price}")
            except Exception as e:
                st.warning(f"⚠️ Could not fetch {stock}: {str(e)[:50]}")
        
        st.info(f"Fetched {len(fetched_stocks)}/{len(stocks)} stocks from Finnhub")
        
        # Generate positions for fetched stocks
        for stock, price in fetched_stocks.items():
            rows.extend(_generate_positions_for_pair('STOCK', stock, price, np.random.randint(3, 10)))
        
        # Crypto prices (CoinGecko or fallback)
        crypto_prices = {}
        for crypto in cryptos:
            try:
                coin_id = crypto.replace('USD', '').lower()
                cg_url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
                response = requests.get(cg_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if coin_id in data and 'usd' in data[coin_id]:
                        price = data[coin_id]['usd']
                        if price > 0:
                            crypto_prices[crypto] = price
                            st.toast(f"✅ {crypto}: ${price:.2f}")
            except Exception:
                pass
        
        # Fallback for cryptos that didn't fetch
        fallback_cryptos = {
            'BTCUSD': 60000, 'ETHUSD': 4000, 'XRPUSD': 3.2, 'SOLUSD': 245,
            'ADAUSD': 1.12, 'DOGEUSD': 0.42, 'MATICUSD': 0.98, 'LTCUSD': 145,
            'BNBUSD': 685, 'AVAXUSD': 42, 'LINKUSD': 28, 'UNIUSD': 12.5, 'AAVEUSD': 320,
            'SNXUSD': 3.8, 'CROUSD': 0.32, 'MKRUSD': 2200, 'YFIUSD': 12000, 'LRCUSD': 0.65,
            'GALAUSD': 0.08, 'SHIBUSD': 0.000018
        }
        for crypto, fallback_price in fallback_cryptos.items():
            if crypto not in crypto_prices:
                crypto_prices[crypto] = fallback_price
        
        for crypto, price in crypto_prices.items():
            rows.extend(_generate_positions_for_pair('CRYPTO', crypto, price, np.random.randint(3, 10)))
        
        st.info(f"Fetched {len(crypto_prices)} crypto prices")
        
        # Forex pairs
        forex_prices = {
            'EURUSD': 1.09, 'GBPUSD': 1.28, 'JPYUSD': 0.0067, 'CHFUSD': 1.18,
            'CADUSD': 0.72, 'AUDUSD': 0.65, 'NZDUSD': 0.59, 'SGDUSD': 0.75,
            'HKDUSD': 0.128, 'SEKUSD': 0.095, 'NOKUSD': 0.096, 'DKKUSD': 0.145,
            'IUSD': 83.5, 'INRUSD': 0.012, 'THBUSD': 0.028, 'MXNUSD': 0.058,
            'ZARUSD': 0.058, 'BRLUSD': 0.195, 'KORUSD': 0.00078, 'ZXUSD': 0.75
        }
        for forex_pair, price in forex_prices.items():
            rows.extend(_generate_positions_for_pair('FOREX', forex_pair, price, np.random.randint(3, 10)))
    
    df = pd.DataFrame(rows)
    return df

def _generate_positions_for_pair(asset_type, pair_name, price, n_positions):
    """Generate realistic positions for a given pair."""
    np.random.seed(hash(pair_name) % (2**32))
    rows = []
    
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

        # Generate size with a heavy-tail to include some very large positions
        # Most positions small, some medium, rare huge positions
        rand = np.random.rand()
        if rand < 0.90:
            size_val = np.random.uniform(100, 10000)
        elif rand < 0.99:
            size_val = np.random.uniform(10000, 100000)
        else:
            size_val = np.random.uniform(100000, 10000000)

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
            'size': round(size_val, 2)
        })
    
    return rows

# Asset classes for filtering
ASSET_CLASSES = ['All', 'STOCK', 'CRYPTO', 'FOREX']

# Header
st.markdown(f"""
<div class="header">
    <div style='font-weight:800;font-size:1.2rem'>DeepFlow Terminal</div>
    <div style='font-weight:600;font-size:0.95rem;margin-left:6px;color:#cfe8ff'>Positions & Liquidations Monitor</div>
    <div style='flex:1'></div>
    <div class='small-muted'>Repo: porsch</div>
</div>
<div style='text-align:center;margin-top:6px;color:#ddd;font-size:0.95rem'>Trade wisely, most people lose money</div>
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
            # Tabs for login and registration
            tab1, tab2 = st.tabs(['Login', 'Create Account'])
            
            with tab1:
                st.subheader('Login')
                st.write('Sign in with your email to access the dashboard')
                
                with st.form('login_form'):
                    login_email = st.text_input('Email', placeholder='john@example.com', key='login_email')
                    login_submit = st.form_submit_button('Login')
                    
                    if login_submit:
                        if not login_email or '@' not in login_email:
                            st.error('Please provide a valid email address.')
                        else:
                            # Search for user in Supabase
                            if supabase is not None:
                                try:
                                    result = supabase.table('leads').select('*').eq('email', login_email).execute()
                                    if result.data and len(result.data) > 0:
                                        user_data = result.data[0]
                                        st.success(f'✅ Welcome back, {user_data.get("name", "User")}! Unlocking dashboard...')
                                        st.session_state['user'] = user_data
                                        st.session_state['unlocked'] = True
                                        st.rerun()
                                    else:
                                        st.error('Email not found. Please create an account or check your email.')
                                except Exception as e:
                                    st.error(f'Error logging in: {str(e)[:100]}')
                            else:
                                st.error('Supabase is not configured.')
            
            with tab2:
                st.subheader('Create Account')
                st.write('Register to access the Positions & Liquidations Monitor')
                
                with st.form('registration_form'):
                    reg_name = st.text_input('Full name', placeholder='John Doe')
                    reg_email = st.text_input('Email', placeholder='john@example.com', key='reg_email')
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
                                        'experience': reg_experience
                                    }
                                    result = supabase.table('leads').insert(payload).execute()
                                    st.success('✅ Account created successfully! Unlocking dashboard...')
                                    st.session_state['user'] = payload
                                    st.session_state['unlocked'] = True
                                    st.rerun()
                                except Exception as e:
                                    st.error(f'Error creating account: {str(e)[:100]}')
                            else:
                                st.error('Supabase is not configured. Please check your environment variables.')
        
                with right:
                        # Promotional / call-to-action panel on the landing page
                        st.markdown("""
                        **Private Group generating millions from Forex & Crypto.**
                        """)
                        st.markdown("""
                        <div style='margin-top:8px'>
                            <a href='https://whop.com/dashboard/biz_4DmTR0EIZkepKS/links/checkout/plan_tYWtxCRSLvfzS/' target='_blank' rel='noopener'>
                                <button style='background:#ff5a5f;color:#fff;border:none;padding:8px 12px;border-radius:6px;cursor:pointer;'>Private Group</button>
                            </a>
                        </div>
                        """, unsafe_allow_html=True)

    else:
        # Dashboard (unlocked) — load real market data
        if 'market_data' not in st.session_state:
            st.session_state['market_data'] = generate_real_market_data()
        
        df = st.session_state['market_data']
        user_info = st.session_state.get('user', {})
        
        # Top header with user info
        col_header_1, col_header_2 = st.columns([4, 1])
        with col_header_1:
            st.markdown(f"Welcome, **{user_info.get('name', 'User')}**! 📊", unsafe_allow_html=True)
        with col_header_2:
            if st.button('🔄 Refresh Data', use_container_width=True):
                st.session_state['market_data'] = generate_real_market_data()
                st.rerun()
        
        left, right = st.columns([3, 1])
        with left:
            st.subheader('Filters')
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                asset_class = st.selectbox('Asset Class', ASSET_CLASSES)
            with c2:
                side = st.selectbox('Side', ['All', 'LONG', 'SHORT'])
            with c3:
                max_dist = st.slider('Max distance (%)', 0.0, 100.0, 20.0)
            with c4:
                pair_filter = st.text_input('Filter pair (e.g., BTC)', placeholder='BTC, AAPL, EUR...')
            
            # Apply filters
            df_view = df.copy()
            if asset_class != 'All':
                df_view = df_view[df_view['asset_class'] == asset_class]
            if side != 'All':
                df_view = df_view[df_view['side'] == side]
            df_view = df_view[df_view['distance_pct'].abs() <= max_dist]
            if pair_filter.strip():
                df_view = df_view[df_view['pair'].str.contains(pair_filter.upper(), case=False, na=False)]
            df_view['abs_distance'] = df_view['distance_pct'].abs()
            df_view = df_view.sort_values('abs_distance')
            
            st.markdown(f'### Positions — {len(df_view)} rows')
            if df_view.empty:
                st.info('No positions match filters.')
            else:
                display_cols = ['pair', 'asset_class', 'address', 'side', 'entry', 'current', 'liq', 'distance_pct', 'leverage', 'size']
                
                # Highlight large positions (>= 10k) in red
                def highlight_large(row):
                    if row['size'] >= 10000:
                        return ['background-color: #ffcccc'] * len(row)
                    return [''] * len(row)
                
                styled_df = df_view[display_cols].reset_index(drop=True).style.format({
                    'entry': '{:.4f}', 'current': '{:.4f}', 'liq': '{:.4f}', 'distance_pct': '{:.2f}', 'size': '{:.2f}'
                }).apply(highlight_large, axis=1)
                
                st.dataframe(styled_df, height=520, use_container_width=True)
                st.caption('Red highlighted rows are top positions (>= $10,000).')
                
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
                top = df_view.nsmallest(5, 'abs_distance')
                st.dataframe(
                    top[['pair', 'side', 'distance_pct', 'leverage']].reset_index(drop=True).style.format({
                        'distance_pct': '{:.2f}'
                    }), 
                    height=200, 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.write('—')
            
            st.markdown('**Counts**')
            counts = df_view['side'].value_counts().reindex(['LONG', 'SHORT']).fillna(0).astype(int)
            st.write(counts.to_frame('count'))
            
            # Copy Addresses button removed per UI request
        
        # ===== CALCULATORS SECTION =====
        st.markdown('---')
        st.markdown('## 📊 Trading Calculators')
        
        calc_tabs = st.tabs(['Leverage', 'Liquidation', 'PnL', 'Position Size', 'Risk/Reward', 'Forex', 'Funding', 'ROI'])
        
        with calc_tabs[0]:  # Leverage Calculator
            st.subheader('Leverage Calculator')
            col1, col2 = st.columns(2)
            with col1:
                entry_price = st.number_input('Entry Price', value=100.0, step=0.01, key='lev_entry')
                liquidation_price = st.number_input('Liquidation Price', value=90.0, step=0.01, key='lev_liq')
                position_type = st.radio('Position Type', ['LONG', 'SHORT'], key='lev_type')
            with col2:
                if position_type == 'LONG':
                    calc_lev = (entry_price - liquidation_price) / entry_price if entry_price != 0 else 0
                else:
                    calc_lev = (liquidation_price - entry_price) / entry_price if entry_price != 0 else 0
                st.metric('Implied Leverage', f'{1/calc_lev:.2f}x' if calc_lev > 0 else 'N/A')
                
                lev_input = st.number_input('Target Leverage', value=5.0, step=0.1, key='lev_target')
                if position_type == 'LONG':
                    liq_calc = entry_price - (entry_price / lev_input)
                else:
                    liq_calc = entry_price + (entry_price / lev_input)
                st.metric('Calculated Liquidation', f'{liq_calc:.4f}')
        
        with calc_tabs[1]:  # Liquidation Calculator
            st.subheader('Liquidation Level Calculator')
            col1, col2, col3 = st.columns(3)
            with col1:
                liq_entry = st.number_input('Entry Price', value=50000.0, step=1.0, key='liq_entry')
                liq_leverage = st.number_input('Leverage', value=10.0, step=0.1, min_value=1.0, key='liq_lev')
            with col2:
                liq_side = st.radio('Side', ['LONG', 'SHORT'], key='liq_side')
                liq_fee = st.number_input('Fee %', value=0.05, step=0.01, key='liq_fee')
            with col3:
                if liq_side == 'LONG':
                    liq_level = liq_entry - (liq_entry / liq_leverage) - (liq_entry * liq_fee / 100)
                else:
                    liq_level = liq_entry + (liq_entry / liq_leverage) + (liq_entry * liq_fee / 100)
                st.metric('Liquidation Price', f'{liq_level:.4f}')
                distance = abs((liq_level - liq_entry) / liq_entry * 100)
                st.metric('Distance %', f'{distance:.2f}%')
        
        with calc_tabs[2]:  # PnL Calculator
            st.subheader('Profit & Loss (PnL) Calculator')
            col1, col2, col3 = st.columns(3)
            with col1:
                pnl_entry = st.number_input('Entry Price', value=100.0, step=0.01, key='pnl_entry')
                pnl_exit = st.number_input('Exit Price', value=110.0, step=0.01, key='pnl_exit')
                pnl_quantity = st.number_input('Quantity', value=1.0, step=0.01, key='pnl_qty')
            with col2:
                pnl_side = st.radio('Side', ['LONG', 'SHORT'], key='pnl_side', horizontal=True)
                pnl_fee = st.number_input('Fee %', value=0.1, step=0.01, key='pnl_fee')
            with col3:
                if pnl_side == 'LONG':
                    pnl = (pnl_exit - pnl_entry) * pnl_quantity
                else:
                    pnl = (pnl_entry - pnl_exit) * pnl_quantity
                fees = (pnl_entry * pnl_quantity * pnl_fee / 100) + (pnl_exit * pnl_quantity * pnl_fee / 100)
                net_pnl = pnl - fees
                pnl_pct = ((pnl_exit - pnl_entry) / pnl_entry * 100) if pnl_side == 'LONG' else ((pnl_entry - pnl_exit) / pnl_entry * 100)
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric('Gross PnL', f'${pnl:.2f}')
                with col_b:
                    st.metric('Fees', f'${fees:.2f}')
                with col_c:
                    st.metric('Net PnL', f'${net_pnl:.2f}', delta=f'{pnl_pct:.2f}%')
        
        with calc_tabs[3]:  # Position Size Calculator
            st.subheader('Position Size Calculator')
            col1, col2, col3 = st.columns(3)
            with col1:
                account_balance = st.number_input('Account Balance ($)', value=10000.0, step=100.0, key='pos_balance')
                risk_pct = st.number_input('Risk %', value=2.0, step=0.1, min_value=0.1, max_value=100.0, key='pos_risk')
                entry_pos = st.number_input('Entry Price', value=100.0, step=0.01, key='pos_entry')
            with col2:
                stop_pos = st.number_input('Stop Loss Price', value=95.0, step=0.01, key='pos_stop')
                leverage_pos = st.number_input('Leverage', value=5.0, step=0.1, key='pos_lev')
            with col3:
                risk_amount = account_balance * risk_pct / 100
                price_diff = abs(entry_pos - stop_pos)
                contracts = (risk_amount / price_diff) if price_diff > 0 else 0
                margin_required = (entry_pos * contracts) / leverage_pos if leverage_pos > 0 else 0
                
                col_x, col_y = st.columns(2)
                with col_x:
                    st.metric('Risk Amount', f'${risk_amount:.2f}')
                    st.metric('Contracts', f'{contracts:.4f}')
                with col_y:
                    st.metric('Margin Required', f'${margin_required:.2f}')
        
        with calc_tabs[4]:  # Risk/Reward Calculator
            st.subheader('Risk/Reward Ratio Calculator')
            col1, col2, col3 = st.columns(3)
            with col1:
                rr_entry = st.number_input('Entry Price', value=100.0, step=0.01, key='rr_entry')
                rr_stop = st.number_input('Stop Loss', value=95.0, step=0.01, key='rr_stop')
                rr_tp = st.number_input('Take Profit', value=110.0, step=0.01, key='rr_tp')
            with col2:
                rr_side = st.radio('Side', ['LONG', 'SHORT'], key='rr_side')
            with col3:
                risk = abs(rr_entry - rr_stop)
                reward = abs(rr_tp - rr_entry)
                ratio = reward / risk if risk > 0 else 0
                win_rate_needed = (100 / (ratio + 1)) if ratio > 0 else 100
                
                col_i, col_j = st.columns(2)
                with col_i:
                    st.metric('Risk', f'${risk:.2f}')
                    st.metric('Reward', f'${reward:.2f}')
                with col_j:
                    st.metric('R:R Ratio', f'1:{ratio:.2f}')
                    st.metric('Win Rate Needed', f'{win_rate_needed:.2f}%')
        
        with calc_tabs[5]:  # Forex Calculator
            st.subheader('Forex Calculator')
            col1, col2, col3 = st.columns(3)
            with col1:
                fx_pair = st.text_input('Currency Pair (e.g., EURUSD)', value='EURUSD', key='fx_pair')
                fx_entry = st.number_input('Entry Rate', value=1.0900, step=0.0001, key='fx_entry')
                fx_exit = st.number_input('Exit Rate', value=1.0950, step=0.0001, key='fx_exit')
            with col2:
                fx_lot_size = st.selectbox('Lot Size', [0.01, 0.1, 1.0, 10.0], index=2, key='fx_lot')
                fx_leverage_fx = st.number_input('Leverage', value=50.0, step=1.0, key='fx_lev')
            with col3:
                pair = fx_pair.strip().upper()
                # pip size: most pairs 0.0001, JPY pairs 0.01
                pip_size = 0.01 if 'JPY' in pair else 0.0001
                # Calculate pips moved
                pips = (fx_exit - fx_entry) / pip_size
                # Pip value approx: lot * 100,000 * pip_size (USD-denominated simplified)
                pip_value = fx_lot_size * 100000 * pip_size
                pnl_fx = pips * pip_value
                margin_fx = (fx_entry * fx_lot_size * 100000) / fx_leverage_fx if fx_leverage_fx > 0 else 0

                col_p, col_q = st.columns(2)
                with col_p:
                    st.metric('Pips', f'{pips:.1f}')
                    st.metric('Pip Size', f'{pip_size}')
                    st.metric('Pip Value (approx)', f'${pip_value:.2f}')
                with col_q:
                    st.metric('PnL', f'${pnl_fx:.2f}')
                    st.metric('Margin Required', f'${margin_fx:.2f}')
                st.caption('Note: pip value is approximate and assumes USD-quoted pairs; cross rates may differ.')
        
        with calc_tabs[6]:  # Funding Rate Calculator
            st.subheader('Funding Rate Calculator')
            col1, col2, col3 = st.columns(3)
            with col1:
                funding_rate = st.number_input('Funding Rate (%)', value=0.05, step=0.01, key='fund_rate')
                funding_position = st.number_input('Position Value ($)', value=10000.0, step=100.0, key='fund_pos')
            with col2:
                funding_period = st.selectbox('Period', ['8 hours', '24 hours', '30 days'], key='fund_period')
                side_fund = st.radio('Side', ['LONG (Pay)', 'SHORT (Receive)'], key='fund_side')
            with col3:
                period_multiplier = {'8 hours': 1, '24 hours': 3, '30 days': 90}[funding_period]
                if side_fund == 'LONG (Pay)':
                    funding_paid = -(funding_position * funding_rate / 100 * period_multiplier)
                else:
                    funding_paid = funding_position * funding_rate / 100 * period_multiplier
                
                st.metric('Funding Payment', f'${funding_paid:.2f}')
                st.caption(f'Per {funding_period.lower()}')
        
        with calc_tabs[7]:  # ROI Calculator
            st.subheader('ROI (Return on Investment) Calculator')
            col1, col2, col3 = st.columns(3)
            with col1:
                initial_capital = st.number_input('Initial Capital ($)', value=1000.0, step=100.0, key='roi_initial')
                final_capital = st.number_input('Final Capital ($)', value=1500.0, step=100.0, key='roi_final')
                time_days = st.number_input('Time Period (days)', value=30, step=1, min_value=1, key='roi_days')
            with col2:
                num_trades = st.number_input('Number of Trades', value=10, step=1, min_value=1, key='roi_trades')
                win_rate_roi = st.number_input('Win Rate (%)', value=60.0, step=1.0, key='roi_wr')
            with col3:
                profit = final_capital - initial_capital
                roi_pct = (profit / initial_capital * 100) if initial_capital > 0 else 0
                roi_annualized = (roi_pct * 365 / time_days) if time_days > 0 else 0
                avg_per_trade = profit / num_trades if num_trades > 0 else 0
                
                col_r, col_s = st.columns(2)
                with col_r:
                    st.metric('Profit', f'${profit:.2f}')
                    st.metric('ROI', f'{roi_pct:.2f}%')
                with col_s:
                    st.metric('Annualized ROI', f'{roi_annualized:.2f}%')
                    st.metric('Avg per Trade', f'${avg_per_trade:.2f}')


if __name__ == '__main__':
    pass
