import streamlit as st
import pandas as pd
import re
import base64
import io
import plotly.express as px

st.set_page_config(page_title="Algotrade Performance Dashboard", layout="wide")

st.title("Algotrade Performance Dashboard")

# Helper function
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

    df = df[df['asked_parity'].astype(float) < 5000]

    df['open_cls'] = abs(df['open_cls'].astype(int))
    df['box_size'] = abs(df['itm_stk'].astype(int) - df['counter'].astype(int))
    df['traded_parity'] = df['traded_parity'].astype(float)
    df['asked_parity'] = df['asked_parity'].astype(float)
    df['parity_diff'] = (df['traded_parity'] - df['asked_parity']) * df['open_cls']
    df['pnl'] = df['parity_diff'] * 75
    df['wrong_right'] = 'right'
    df.loc[df['traded_parity'] <= df['asked_parity'], 'wrong_right'] = 'wrong'
    df['gross_flow'] = df['traded_parity'] * df['open_cls'] * 75

    summary = []
    for i in sorted(df['box_size'].unique()):
        df1 = df[df['box_size'] == i]
        total = df1['open_cls'].sum()
        correct = df1[df1['wrong_right'] == 'right']['open_cls'].sum()
        wrong = df1[df1['wrong_right'] == 'wrong']['open_cls'].sum()
        pos_alpha = df1[df1['wrong_right'] == 'right']['parity_diff'].sum() * 75
        neg_alpha = df1[df1['wrong_right'] == 'wrong']['parity_diff'].sum() * 75
        net_alpha = pos_alpha + neg_alpha
        gross_flow = df1['gross_flow'].sum()
        summary.append((i, total, correct, wrong, pos_alpha, neg_alpha, net_alpha, gross_flow))

    df_summary = pd.DataFrame(summary, columns=[
        'box_size', 'total_trades', 'correct_trades', 'wrong_trades',
        'positive_alpha', 'negative_alpha', 'net_alpha', 'gross_flow'
    ])

    return df, df_summary

# Upload section
uploaded_file = st.file_uploader("Upload Trade File (.txt)", type=['txt'])

if uploaded_file:
    df_traded, df_summary = parse_data(uploaded_file)

    # Dropdown for filtering (optional)
    box_sizes = sorted(df_summary['box_size'].unique())
    selected_box = st.selectbox("Select box size (optional)", options=["All"] + box_sizes)

    if selected_box != "All":
        df_filtered = df_summary[df_summary['box_size'] == selected_box]
    else:
        df_filtered = df_summary

    # Display summary table
    st.subheader("Summary Table")
    st.dataframe(df_filtered)

    # Download CSV
    csv = df_summary.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "processed_data.csv", "text/csv")

    # Charts
    st.subheader("Alpha Breakdown by Box Size")
    fig1 = px.bar(df_summary, x='box_size', y=['positive_alpha', 'negative_alpha'],
                  title='Alpha Breakdown by Box Size',
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
