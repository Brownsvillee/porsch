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

def generate_demo_positions(pairs, n_per_pair=40, seed=42):
    np.random.seed(seed)
    rows = []
    for pair in pairs:
        base = {'BTC-USD':60000,'ETH-USD':4000,'ZEC-USD':620,'DAX-USD':16000}.get(pair,1000)
        for i in range(n_per_pair):
            side = np.random.choice(['LONG','SHORT'], p=[0.6,0.4])
            entry = base * (1 + np.random.normal(0, 0.02))
            leverage = int(np.random.choice([5,10,20,50,75,100], p=[0.1,0.15,0.3,0.25,0.1,0.1]))
            if side == 'LONG':
                liq = entry - (entry / leverage) * (0.9 + np.random.rand()*0.6)
            else:
                liq = entry + (entry / leverage) * (0.9 + np.random.rand()*0.6)
            current = entry * (1 + np.random.normal(0, 0.015))
            distance_pct = (liq - current) / current * 100 if side == 'LONG' else (current - liq) / current * 100
            rows.append({'pair':pair,'address':f'0x{np.random.randint(10**7):x}','side':side,'entry':round(entry,2),'liq':round(liq,2),'current':round(current,2),'distance_pct':round(distance_pct,2),'leverage':leverage,'size':round(abs(np.random.normal(0.5,2.0))*10,4)})
    return pd.DataFrame(rows)

DEFAULT_PAIRS = ['BTC-USD','ETH-USD','ZEC-USD','DAX-USD']

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
        left, right = st.columns([3,1])
        with left:
            st.subheader('Upload CSV (required)')
            uploaded = st.file_uploader('Upload CSV with columns: pair,address,side,entry,liq,current,distance_pct,leverage,size', type=['csv'])
            if uploaded is not None:
                try:
                    temp_df = pd.read_csv(uploaded)
                    st.session_state['uploaded_df_preview'] = temp_df.head(5)
                    st.success('CSV parsed successfully — please complete the lead form to unlock the dashboard.')
                except Exception as e:
                    st.error(f'Failed to parse CSV: {e}')
                    temp_df = None
            else:
                temp_df = None

            st.markdown('---')
            st.subheader('Lead Access Form (required)')
            with st.form('unlock_form'):
                lead_name = st.text_input('Full name')
                lead_phone = st.text_input('Phone (international format)')
                lead_email = st.text_input('Email')
                lead_experience = st.selectbox('Experience level', ['Retail (< $10k)', 'Pro Trader (>$50k)', 'Institutional / Quant'])
                save_lead = st.checkbox('Save lead to Supabase (if configured)', value=False)
                submit = st.form_submit_button('Request access')
                if submit:
                    # validate lead fields
                    if not lead_name or not (lead_email or lead_phone):
                        st.error('Please provide your name and at least an email or phone number.')
                    elif temp_df is None:
                        st.error('Please upload a valid CSV before requesting access.')
                    else:
                        # normalize and validate CSV
                        df_norm = normalize_df(temp_df)
                        # require at least one non-null address and liq/current
                        if df_norm['address'].isna().all() or df_norm['liq'].isna().all() or df_norm['current'].isna().all():
                            st.error('Uploaded CSV is missing required numeric fields (address, liq, current). Please check your file.')
                        else:
                            # Save lead to Supabase if requested
                            if save_lead and supabase is not None:
                                try:
                                    payload = {'name':lead_name,'email':lead_email,'phone':lead_phone,'experience':lead_experience}
                                    supabase.table('leads').insert(payload).execute()
                                    st.success('Lead saved to Supabase.')
                                except Exception as e:
                                    st.warning(f'Failed to save lead to Supabase: {e}')
                            # store data and unlock
                            st.session_state['data'] = df_norm
                            st.session_state['lead'] = {'name':lead_name,'email':lead_email,'phone':lead_phone,'experience':lead_experience}
                            st.session_state['unlocked'] = True
                            st.success('Access granted — loading dashboard...')
                            st.experimental_rerun()

        with right:
            st.subheader('CSV preview')
            if 'uploaded_df_preview' in st.session_state:
                st.dataframe(st.session_state['uploaded_df_preview'])
            else:
                st.info('Upload a CSV to preview its first rows here.')

    else:
        # Dashboard (unlocked)
        df = st.session_state.get('data', pd.DataFrame(columns=['pair','address','side','entry','liq','current','distance_pct','leverage','size']))
        # derive available pairs from uploaded data
        pairs = sorted(df['pair'].dropna().unique())
        if not pairs:
            pairs = ['ALL']
        left, right = st.columns([3,1])
        with left:
            st.subheader('Filters')
            pair = st.selectbox('Pair', ['ALL'] + pairs, index=1 if len(pairs)>0 else 0)
            side = st.selectbox('Side', ['All','LONG','SHORT'])
            max_dist = st.slider('Max distance to liquidation (%)', 0.0, 100.0, 15.0)

            # apply filters
            df_view = df.copy()
            if pair != 'ALL':
                df_view = df_view[df_view['pair'] == pair]
            if side != 'All':
                df_view = df_view[df_view['side'] == side]
            df_view = df_view[df_view['distance_pct'].abs() <= max_dist]
            df_view['abs_distance'] = df_view['distance_pct'].abs()
            df_view = df_view.sort_values('abs_distance')

            st.markdown(f'### Positions — {len(df_view)} rows')
            if df_view.empty:
                st.info('No positions match filters.')
            else:
                display_cols = ['address','side','entry','current','liq','distance_pct','leverage','size']
                st.dataframe(df_view[display_cols].reset_index(drop=True).style.format({'entry':'{:.2f}','current':'{:.2f}','liq':'{:.2f}','distance_pct':'{:.2f}','size':'{:.4f}'}), height=520)
                chart = alt.Chart(df_view.reset_index()).mark_bar().encode(
                    x=alt.X('distance_pct:Q', title='Distance to Liquidation (%)'),
                    y=alt.Y('address:N', sort='-x', title='Address'),
                    color=alt.Color('side:N', scale=alt.Scale(domain=['LONG','SHORT'], range=['#27ae60','#e50914'])),
                    tooltip=['address','side','entry','current','liq','distance_pct','leverage','size']
                ).properties(height=420)
                st.altair_chart(chart, use_container_width=True)

        with right:
            st.subheader('Top & Actions')
            if not df_view.empty:
                top = df_view.nsmallest(10,'abs_distance')
                st.table(top[['address','side','current','liq','distance_pct','leverage']].reset_index(drop=True).style.format({'current':'{:.2f}','liq':'{:.2f}','distance_pct':'{:.2f}'}))
            else:
                st.write('—')

            st.markdown('**Counts**')
            counts = df_view['side'].value_counts().reindex(['LONG','SHORT']).fillna(0).astype(int)
            st.write(counts.to_frame('count'))

            if st.button('Copy top addresses'):
                if not df_view.empty:
                    st.code('\n'.join(df_view['address'].head(50).tolist()))
                    st.success('Addresses shown above — copy manually.')
                else:
                    st.info('No addresses to copy.')


st.markdown('<div style="padding:8px 18px;color:rgba(255,255,255,0.6);font-size:0.9rem">Provide a CSV with real positions to use this dashboard. Lead form required to unlock.</div>', unsafe_allow_html=True)

if __name__ == '__main__':
    pass
