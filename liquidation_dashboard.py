import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import time
import secrets

st.set_page_config(page_title="Liquidation Dashboard", layout="wide", initial_sidebar_state="collapsed")

CSS = """
<style>
/* Fixed header that stays at the top */
.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  background: linear-gradient(90deg, rgba(6,10,18,0.95), rgba(12,18,30,0.95));
  color: #fff;
  padding: 10px 18px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}

/* Push page content down so header doesn't cover it */
.content {
  margin-top: 78px;
  padding: 12px 18px 40px 18px;
}

.small-muted {color: rgba(255,255,255,0.65); font-size:0.9rem}
.pos-table {font-family: monospace}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# Helper: simulate dataset
def generate_demo_positions(pairs, n_per_pair=30, seed=None):
    if seed is not None:
        np.random.seed(seed)
    rows = []
    for pair in pairs:
        # choose a current price per pair (simulate different scales)
        base = {
            'BTC-USD': 60000,
            'ETH-USD': 4000,
            'ZEC-USD': 620,
            'XBT-USD': 60000,
            'DAX-USD': 16000
        }.get(pair, 1000)
        for i in range(n_per_pair):
            side = np.random.choice(['LONG', 'SHORT'], p=[0.6, 0.4])
            entry = base * (1 + np.random.normal(0, 0.02))
            leverage = int(np.random.choice([5,10,20,50,75,100,125,200], p=[0.1,0.15,0.2,0.2,0.15,0.1,0.06,0.04]))
            # For demo: liquidation distance depends on leverage
            if side == 'LONG':
                liq = entry - (entry / leverage) * (0.9 + np.random.rand()*0.6)
            else:
                liq = entry + (entry / leverage) * (0.9 + np.random.rand()*0.6)
            current = entry * (1 + np.random.normal(0, 0.015))
            distance_pct = (liq - current) / current * 100 if side == 'LONG' else (current - liq) / current * 100
            size = round(abs(np.random.normal(0.5, 2.0)) * 10, 4)
            addr = '0x' + secrets.token_hex(8)
            rows.append({
                'pair': pair,
                'address': addr,
                'side': side,
                'entry': round(entry, 2),
                'liq': round(liq, 2),
                'current': round(current, 2),
                'distance_pct': round(distance_pct, 2),
                'leverage': leverage,
                'size': size
            })
    return pd.DataFrame(rows)

# Default pairs available
DEFAULT_PAIRS = ['BTC-USD', 'ETH-USD', 'ZEC-USD', 'DAX-USD']

# Header: fixed with controls
st.markdown(
    f"""
    <div class="header">
      <div style='font-weight:700;font-size:1.1rem'>Liquidation & Positions Monitor</div>
      <div class='small-muted'>| Live demo · select pair to filter positions</div>
      <div style='flex:1'></div>
    </div>
    """,
    unsafe_allow_html=True
)

# Main content container
with st.container():
    st.markdown('<div class="content"></div>', unsafe_allow_html=True)

# Create a real layout inside the content area
# Use a second container so the fixed header doesn't overlap controls
content = st.container()
with content:
    col_left, col_right = st.columns([3, 1])
    with col_left:
        st.subheader('Controls & Data')
        # Pair selector, CSV upload, refresh, filters
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            pair = st.selectbox('Pair', DEFAULT_PAIRS, index=0)
        with c2:
            uploaded = st.file_uploader('Upload CSV to override demo data (optional)', type=['csv'])
        with c3:
            if st.button('Refresh data'):
                st.experimental_rerun()

        st.write('')
        st.markdown('**Filters**')
        f1, f2 = st.columns([2, 1])
        with f1:
            side_filter = st.selectbox('Side', ['All', 'LONG', 'SHORT'])
        with f2:
            max_distance = st.slider('Max distance to liq (%)', min_value=0.0, max_value=50.0, value=15.0)

        # Load or simulate data
        if uploaded is not None:
            try:
                df_all = pd.read_csv(uploaded)
                st.success('CSV loaded — ensure it has columns: pair,address,side,entry,liq,current,leverage,size')
            except Exception as e:
                st.error(f'Failed to parse CSV: {e}')
                df_all = generate_demo_positions(DEFAULT_PAIRS, n_per_pair=30, seed=123)
        else:
            # cached/demo
            if 'demo_df' not in st.session_state:
                st.session_state['demo_df'] = generate_demo_positions(DEFAULT_PAIRS, n_per_pair=50, seed=42)
            df_all = st.session_state['demo_df']

        # Normalize column names if uploaded
        expected_cols = {'pair','address','side','entry','liq','current','distance_pct','leverage','size'}
        if not expected_cols.issubset(set(df_all.columns)):
            # attempt basic conversions
            if 'distance' in df_all.columns and 'distance_pct' not in df_all.columns:
                df_all['distance_pct'] = df_all['distance']

        # Filter by pair & side & distance
        df = df_all[df_all['pair'] == pair].copy()
        if side_filter != 'All':
            df = df[df['side'] == side_filter]
        df = df[df['distance_pct'].abs() <= max_distance]

        # Sort by closest to liq (ascending absolute distance)
        df['abs_distance'] = df['distance_pct'].abs()
        df = df.sort_values('abs_distance')

        st.markdown(f"### Positions for {pair} — showing {len(df)} positions")
        if df.empty:
            st.info('No positions matching the filters (try increasing max distance or uploading data).')
        else:
            # Display table (interactive)
            show_cols = ['address', 'side', 'entry', 'current', 'liq', 'distance_pct', 'leverage', 'size']
            st.dataframe(df[show_cols].reset_index(drop=True).style.format({
                'entry':'{:.2f}','current':'{:.2f}','liq':'{:.2f}','distance_pct':'{:.2f}','size':'{:.4f}'
            }), height=520)

            # Chart: distances, color by side
            chart = alt.Chart(df.reset_index()).mark_bar().encode(
                x=alt.X('distance_pct:Q', title='Distance to Liquidation (%)'),
                y=alt.Y('address:N', sort='-x', title='Address'),
                color=alt.Color('side:N', scale=alt.Scale(domain=['LONG','SHORT'], range=['#27ae60','#e50914'])),
                tooltip=['address','side','entry','current','liq','distance_pct','leverage','size']
            ).properties(height=400)
            st.altair_chart(chart, use_container_width=True)

    with col_right:
        st.subheader('Summary')
        st.markdown('**Closest to liquidation (top 10)**')
        if not df.empty:
            top10 = df.nsmallest(10, 'abs_distance')
            st.table(top10[['address','side','current','liq','distance_pct','leverage']].reset_index(drop=True).style.format({
                'current':'{:.2f}','liq':'{:.2f}','distance_pct':'{:.2f}'
            }))
        else:
            st.write('—')

        st.markdown('**Counts**')
        counts = df['side'].value_counts().reindex(['LONG','SHORT']).fillna(0).astype(int)
        st.write(counts.to_frame('count'))

        st.markdown('**Quick actions**')
        if st.button('Copy top addresses'):
            if not df.empty:
                top_addrs = '\n'.join(df['address'].head(20).tolist())
                st.code(top_addrs)
                st.success('Copied list shown — copy it manually from the box above.')
            else:
                st.info('No addresses to copy.')

        st.markdown('**Auto refresh**')
        auto = st.checkbox('Enable auto-refresh (every 10s)', value=False)
        if auto:
            st.experimental_rerun()

if __name__ == '__main__':
    pass
