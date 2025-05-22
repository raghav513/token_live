import streamlit as st
import pandas as pd
import re
import base64
import io
import plotly.express as px

st.set_page_config(page_title="Box Performance Dashboard", layout="wide")
st.title("📦 Box Performance Dashboard")

# Helper Function: Extract Lot Size
def get_lot_size_from_expiry(expiry_str):
    try:
        instrument = re.findall(r'[A-Z]+', expiry_str)[0]
    except IndexError:
        return None

    lot_size_map = {
        'NIFTY': 75,
        'BANKNIFTY': 30,
        'MIDCPNIFTY': 120,
        'FINNIFTY': 65
    }
    return lot_size_map.get(instrument)

# Main Data Parser
def parse_data(file):
    content = file.read()
    decoded = io.StringIO(content.decode('utf-8'))
    data = pd.read_csv(decoded, on_bad_lines='skip')
    data.columns = ['date', 'status', 'type', 'message']
    df = data[data['type'] == 'ALGOTRADE'].copy()

    pattern = (
        r"BOX\s+(\w+\d*)-(\d+)-(\d+)(CE|PE)\s+Strategy\s+Trade\s+Confirmed\s+Qty\s+([-+]?\d+)\s+@\s+([-+]?\d*\.\d+|\d+)\s+\[Parity\s+Was\s+([-+]?\d*\.\d+|\d+)"
    )
    df_extracted = df['message'].str.extract(pattern)
    df_extracted.columns = ['expiry', 'itm_stk', 'counter', 'option_type', 'open_cls', 'traded_parity', 'asked_parity']
    df = pd.concat([df, df_extracted], axis=1)

    # Clean numeric data
    for col in ['open_cls', 'itm_stk', 'counter']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    for col in ['traded_parity', 'asked_parity']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=['expiry', 'open_cls', 'itm_stk', 'counter', 'traded_parity', 'asked_parity'])
    df = df[df['asked_parity'] < 5000]

    expiry_value = df['expiry'].iloc[0]
    lot_size = get_lot_size_from_expiry(expiry_value)

    if lot_size is None:
        st.error(f"❌ Unknown instrument in expiry string: {expiry_value}")
        return pd.DataFrame(), pd.DataFrame()

    # Calculations
    df['box_size'] = abs(df['itm_stk'] - df['counter'])
    df['parity_diff'] = (df['traded_parity'] - df['asked_parity'])*abs(df['open_cls'])
    df['pnl'] = df['parity_diff'] * lot_size 
    df['wrong_right'] = df['traded_parity'] > df['asked_parity']
    df['wrong_right'] = df['wrong_right'].map({True: 'right', False: 'wrong'})
    df['gross_flow'] = df['traded_parity'] * abs(df['open_cls']) * lot_size

    # Summary Table
    summary = []
    for i in sorted(df['box_size'].unique()):
        df1 = df[df['box_size'] == i]
        total = df1['open_cls'].abs().sum()
        correct = df1[df1['wrong_right'] == 'right']['open_cls'].abs().sum()
        wrong = df1[df1['wrong_right'] == 'wrong']['open_cls'].abs().sum()
        pos_alpha = df1[df1['wrong_right'] == 'right']['parity_diff'].sum() * lot_size
        neg_alpha = df1[df1['wrong_right'] == 'wrong']['parity_diff'].sum() * lot_size
        net_alpha = pos_alpha + neg_alpha
        gross_flow = df1['gross_flow'].sum()
        summary.append((i, total, correct, wrong, pos_alpha, neg_alpha, net_alpha, gross_flow))

    df_summary = pd.DataFrame(summary, columns=[
        'box_size', 'total_trades', 'correct_trades', 'wrong_trades',
        'positive_alpha', 'negative_alpha', 'net_alpha', 'gross_flow'
    ])

    return df, df_summary

# File Upload
uploaded_file = st.file_uploader("📤 Upload Trade File (.txt)", type=['txt'])

if uploaded_file:
    df_traded, df_summary = parse_data(uploaded_file)

    if not df_traded.empty:
        # Tabs
        tab1, tab2, tab3 = st.tabs(["📋 Summary", "📈 Charts", "📊 Raw Data"])

        # Tab 1: Summary
        with tab1:
            exp = df_traded['expiry'].iloc[0]
            st.subheader(f"Summary Table for Expiry: `{exp}`")
            selected_box = st.selectbox("Filter by Box Size (optional)", options=["All"] + sorted(df_summary['box_size'].unique()))
            if selected_box != "All":
                df_filtered = df_summary[df_summary['box_size'] == selected_box]
            else:
                df_filtered = df_summary
            st.dataframe(df_filtered, use_container_width=True)

            csv = df_summary.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Summary CSV", csv, "summary.csv", "text/csv")

        # Tab 2: Charts
        with tab2:
            st.subheader("Alpha Breakdown by Box Size")
            fig1 = px.bar(df_summary, x='box_size', y=['positive_alpha', 'negative_alpha'],
                          barmode='group',
                          labels={'value': 'Alpha', 'box_size': 'Box Size', 'variable': 'Alpha Type'})
            st.plotly_chart(fig1, use_container_width=True)

            st.subheader("Gross Flow by Box Size")
            fig2 = px.bar(df_summary, x='box_size', y='gross_flow',
                          title='Gross Flow by Box Size',
                          text_auto=True)
            st.plotly_chart(fig2, use_container_width=True)

            st.subheader("Distribution of Traded Parity")
            fig3 = px.histogram(df_traded, x='traded_parity', nbins=30,
                                title='Distribution of Traded Parity')
            st.plotly_chart(fig3, use_container_width=True)

        # Tab 3: Raw Data
        with tab3:
            st.subheader("Raw Parsed Trade Data")
            st.dataframe(df_traded, use_container_width=True)
            raw_csv = df_traded.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Raw Data CSV", raw_csv, "raw_trades.csv", "text/csv")
