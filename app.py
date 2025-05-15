import streamlit as st
import pandas as pd
import datetime
import re
import base64
import io
import plotly.express as px
from nselib import derivatives
import pandas_market_calendars as mcal

st.title("STOCK CR TOKEN")
st.write("This app generates stock CR token.")

st.sidebar.title("Navigation")
page = st.sidebar.radio("Select Page", "Stock CR Token")

if 'm2m' not in st.session_state:
    st.session_state.m2m = None

def is_trading_day(date):
    nse = mcal.get_calendar('NSE')
    schedule = nse.schedule(start_date=date, end_date=date)
    return not schedule.empty

def run_analysis(date_str, month, oi_threshold, atm_percentage):
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d-%m-%Y')

        data = derivatives.fno_bhav_copy(formatted_date)
        if data.empty:
            return None, "Unable to fetch Bhavcopy from NSE. Please upload manually."

        return run_analysis_common(data, month, oi_threshold, atm_percentage)

    except Exception as e:
        return None, f"Error: {str(e)}"

def run_analysis_common(data, month, oi_threshold, atm_percentage):
    try:
        data = data[data['FinInstrmNm'].str.contains(month)].copy()
        if data.empty:
            return None, f"No contracts found for {month}."

        data['open_int'] = data['OpnIntrst'] / data['NewBrdLotQty']
        fut = data[data['FinInstrmNm'].str.contains(f'{month}FUT')].copy()
        FUT = fut['FinInstrmNm'].copy()

        mask = (
            ((data['StrkPric'] >= data['UndrlygPric']) & (data['OptnTp'] == 'PE')) |
            ((data['StrkPric'] <= data['UndrlygPric']) & (data['OptnTp'] == 'CE'))
        )
        df = data[mask].copy()
        if df.empty:
            return None, "No matching data after applying filters."

        atm_decimal = atm_percentage / 100
        df['atm_con'] = df.apply(
            lambda row: 'True' if (
                row['StrkPric'] <= row['UndrlygPric'] - (atm_decimal * row['UndrlygPric']) or
                row['StrkPric'] >= row['UndrlygPric'] + (atm_decimal * row['UndrlygPric'])
            ) else 'False',
            axis=1
        )

        mask01 = df[df['atm_con'] == "True"]
        mask01 = mask01[mask01['open_int'] > oi_threshold]
        mask02 = df[df['atm_con'] == "False"]
        df1 = pd.merge(mask01, mask02, how='outer')
        if df1.empty:
            return None, "No data after applying OI threshold filter."

        df2 = pd.DataFrame(df1['FinInstrmNm'])
        df2['copy_fin'] = df2['FinInstrmNm'].str[:-2] + 'PE'
        df2['FinInstrmNm'] = df2['FinInstrmNm'].str[:-2] + 'CE'
        df2['FinInstrmNm'] = 'NRML|' + df2['FinInstrmNm']
        df2['copy_fin'] = 'NRML|' + df2['copy_fin']

        if not FUT.empty:
            FUT_df = pd.DataFrame({'fut': 'NRML|' + FUT})
        else:
            FUT_df = pd.DataFrame({'fut': []})

        ce_df = pd.DataFrame({'All Columns': df2['FinInstrmNm']})
        pe_df = pd.DataFrame({'All Columns': df2['copy_fin']})
        fut_df = pd.DataFrame({'All Columns': FUT_df['fut']})
        df_combined = pd.concat([ce_df, pe_df, fut_df], ignore_index=True)

        df_filtered = df_combined[~df_combined['All Columns'].str.contains('NIFTY', na=False)].copy()
        mask = pd.Series(False, index=df_filtered.index)
        for col in df_filtered.columns:
            if df_filtered[col].dtype == object:
                mask |= df_filtered[col].str.contains('\.', na=False)
        df5 = df_filtered[~mask]
        df5 = df5.sort_values(by='All Columns')

        return df5, None

    except Exception as e:
        return None, f"Error in processing: {str(e)}"

# Sidebar controls
derivatives_sidebar = st.sidebar.expander("Token Parameters", expanded=True)
with derivatives_sidebar:
    today = datetime.date.today()
    date = st.date_input("Select Date", today)
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    selected_month = st.selectbox("Select Expiry Month", months, index=today.month - 1)
    oi_threshold = st.number_input("OI Threshold", min_value=1, value=4)
    atm_percentage = st.slider("ATM Range Percentage", min_value=1, max_value=20, value=8)
    sort_ascending = st.checkbox("Sort Ascending", value=True)

if st.button("Generate Token"):
    if not is_trading_day(date):
        st.warning(f"Selected date ({date}) may not be a trading day.")

    date_str = date.strftime('%Y-%m-%d')

    with st.spinner("Processing data..."):
        result_df, error = run_analysis(date_str, selected_month, oi_threshold, atm_percentage)

    if error and "upload manually" in error:
        st.warning(error)
        uploaded_file = st.file_uploader("Upload Bhavcopy CSV File", type=["csv"])
        if uploaded_file:
            uploaded_data = pd.read_csv(uploaded_file)
            with st.spinner("Processing uploaded file..."):
                result_df, error = run_analysis_common(uploaded_data, selected_month, oi_threshold, atm_percentage)

    if error:
        st.error(error)
    elif result_df is not None:
        result_df = result_df.sort_values(by='All Columns', ascending=sort_ascending)
        st.success("Token Generated successfully!")

        st.subheader("Show Token")
        st.dataframe(result_df)

        futures_count = result_df['All Columns'].str.contains('FUT$', regex=True).sum()
        ce_count = result_df['All Columns'].str.contains('CE$', regex=True).sum()
        pe_count = result_df['All Columns'].str.contains('PE$', regex=True).sum()

        st.subheader("Download Options")
        col1, col2 = st.columns(2)
        with col1:
            csv = result_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, f"stock_crtoken_{date_str}_{selected_month}.csv", "text/csv")
        with col2:
            text_content = "\n".join(result_df['All Columns'].tolist()).encode('utf-8')
            st.download_button("Download TXT", text_content, f"stock_crtoken_{date_str}_{selected_month}.txt", "text/plain")

        st.subheader("Summary")
        st.write(f"Total tokens: {len(result_df)}")
        st.write(f"- Futures: {futures_count}")
        st.write(f"- Call Options (CE): {ce_count}")
        st.write(f"- Put Options (PE): {pe_count}")
        st.write(f"Parameters: Date={date}, Month={selected_month}, OI Threshold={oi_threshold}, ATM={atm_percentage}%")
        st.write(f"Sorted: {'Ascending' if sort_ascending else 'Descending'}")

        st.subheader("Distribution")
        chart_data = pd.DataFrame({
            'Type': ['Futures', 'Call Options', 'Put Options'],
            'Count': [futures_count, ce_count, pe_count]
        })
        st.bar_chart(chart_data.set_index('Type'))

with st.expander("About Stock CR Token"):
    st.info("""
    This tool retrieves NSE derivatives data and filters based on:
    - Expiry month
    - Open Interest (OI) threshold
    - ATM deviation from underlying price
    - PE/CE logic
    """)

    st.subheader("ATM Range Explanation")
    st.info(f"""
    - A {atm_percentage}% setting includes strikes more than {atm_percentage}% above or below the underlying price only if OI > threshold.
    - Lower % = tighter ATM range; higher % = broader selection.
    """)

st.markdown("---")
st.markdown("Trading Analysis Dashboard | Created with Streamlit")
