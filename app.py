import streamlit as st
import pandas as pd
import datetime
import pandas_market_calendars as mcal
from nselib import derivatives

st.title("📈 STOCK CR TOKEN")
st.write("Generate stock CR token from NSE BhavCopy. If automatic fetch fails, upload your own CSV file.")

# Sidebar inputs
st.sidebar.title("Token Parameters")
date = st.sidebar.date_input("Select Date", datetime.date.today())
months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
selected_month = st.sidebar.selectbox("Select Expiry Month", months, index=datetime.datetime.now().month - 1)
oi_threshold = st.sidebar.number_input("OI Threshold", min_value=1, value=4)
atm_percentage = st.sidebar.slider("ATM Range %", 1, 20, 8)
sort_ascending = st.sidebar.checkbox("Sort Ascending", value=True)

def is_trading_day(date):
    nse = mcal.get_calendar('NSE')
    schedule = nse.schedule(start_date=date, end_date=date)
    return not schedule.empty

def process_bhavcopy(data, month, oi_threshold, atm_percentage):
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
            return None, "No data after applying CE/PE filter."

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
            return None, "No data after OI filtering."

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
        df_final = df_filtered[~mask]
        df_final = df_final.sort_values(by='All Columns')

        return df_final, None

    except Exception as e:
        return None, f"Processing error: {str(e)}"

# Trigger logic
if st.button("Generate Token"):
    date_str = date.strftime('%Y-%m-%d')

    st.info(f"Checking data for: {date_str}")
    with st.spinner("Fetching BhavCopy..."):
        try:
            formatted_date = date.strftime('%d-%m-%Y')
            data = derivatives.fno_bhav_copy(formatted_date)
        except Exception as e:
            data = pd.DataFrame()

    if data.empty:
        st.warning("⚠️ Unable to fetch BhavCopy from NSE. Please upload it manually below.")
        uploaded_file = st.file_uploader("Upload BhavCopy CSV", type=['csv'])
        if uploaded_file:
            try:
                data = pd.read_csv(uploaded_file)
                result_df, error = process_bhavcopy(data, selected_month, oi_threshold, atm_percentage)
            except Exception as e:
                st.error(f"Upload error: {e}")
                result_df, error = None, str(e)
        else:
            result_df, error = None, "No file uploaded."
    else:
        result_df, error = process_bhavcopy(data, selected_month, oi_threshold, atm_percentage)

    # Display results
    if error:
        st.error(error)
    elif result_df is not None:
        result_df = result_df.sort_values(by='All Columns', ascending=sort_ascending)

        st.success("✅ Token Generated")
        st.dataframe(result_df)

        futures_count = result_df['All Columns'].str.contains('FUT$').sum()
        ce_count = result_df['All Columns'].str.contains('CE$').sum()
        pe_count = result_df['All Columns'].str.contains('PE$').sum()

        col1, col2 = st.columns(2)
        with col1:
            csv = result_df.to_csv(index=False).encode()
            st.download_button("Download CSV", csv, "stock_tokens.csv", "text/csv")
        with col2:
            text = "\n".join(result_df['All Columns'].tolist()).encode()
            st.download_button("Download TXT", text, "stock_tokens.txt", "text/plain")

        st.markdown("### 📊 Token Summary")
        st.write(f"Total: {len(result_df)} | Futures: {futures_count} | CE: {ce_count} | PE: {pe_count}")
        st.bar_chart(pd.DataFrame({
            "Type": ["Futures", "CE", "PE"],
            "Count": [futures_count, ce_count, pe_count]
        }).set_index("Type"))

st.markdown("---")
st.info("If automatic BhavCopy fetch fails, you can download it from [NSE Website](https://www.nseindia.com/all-reports-derivatives) and upload here.")
