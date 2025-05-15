import streamlit as st
import pandas as pd
import io

st.title("NSE FO BhavCopy Processor")

# --- Sidebar Inputs ---
month = st.sidebar.text_input("Enter Month (e.g., MAY)", "MAY").upper()
oi = st.sidebar.number_input("Open Interest Threshold", value=4)

uploaded_file = st.file_uploader("Upload BhavCopy CSV", type=['csv'])

if uploaded_file is not None:
    # Read the uploaded CSV
    data = pd.read_csv(uploaded_file)

    try:
        # Filter by month
        data = data[data['FinInstrmNm'].str.contains(month)].copy()
        data['open_int'] = data['OpnIntrst'] / data['NewBrdLotQty']

        # Futures
        fut = data[data['FinInstrmNm'].str.contains(f'{month}FUT')].copy()
        FUT = fut['FinInstrmNm'].copy()

        # ITM/OTM mask
        mask = (
            ((data['StrkPric'] >= data['UndrlygPric']) & (data['OptnTp'] == 'PE')) |
            ((data['StrkPric'] <= data['UndrlygPric']) & (data['OptnTp'] == 'CE'))
        )
        df = data[mask].copy()

        # ATM condition
        df['atm_con'] = df.apply(
            lambda row: 'True' if (
                row['StrkPric'] <= row['UndrlygPric'] - (0.08 * row['UndrlygPric']) or
                row['StrkPric'] >= row['UndrlygPric'] + (0.08 * row['UndrlygPric'])
            ) else 'False',
            axis=1
        )

        # Filter based on atm_con and open_int
        mask01 = df[(df['atm_con'] == "True") & (df['open_int'] > oi)]
        mask02 = df[df['atm_con'] == "False"]
        df1 = pd.merge(mask01, mask02, how='outer')

        # Prepare option tokens
        df2 = pd.DataFrame(df1['FinInstrmNm'])
        df2['copy_fin'] = df2['FinInstrmNm'].str[:-2] + 'PE'
        df2['FinInstrmNm'] = df2['FinInstrmNm'].str[:-2] + 'CE'
        df2['FinInstrmNm'] = 'NRML|' + df2['FinInstrmNm']
        df2['copy_fin'] = 'NRML|' + df2['copy_fin']

        # Prepare futures
        FUT = pd.DataFrame(FUT).rename(columns={'FinInstrmNm': 'fut'})
        FUT['fut'] = 'NRML|' + FUT['fut']
        FUT = FUT.sort_values(by=['fut']).reset_index(drop=True)

        # Merge option and futures data
        df3 = pd.concat([df2, FUT], axis=0)
        df3 = df3.sort_values(by=['FinInstrmNm']).reset_index(drop=True)

        # Remove 'NIFTY' rows
        df4 = df3[~df3['FinInstrmNm'].str.contains('NIFTY', na=False)].copy()
        df4 = df4[~df4['fut'].str.contains('NIFTY', na=False)].copy()

        # Flatten
        df_new = pd.DataFrame(df4.values.flatten(), columns=['All Columns']).dropna()

        # Remove rows containing "."
        mask = pd.Series(False, index=df_new.index)
        mask |= df_new['All Columns'].str.contains('\.', na=False)
        df5 = df_new[~mask]

        # Display result
        st.success("Processing complete.")
        st.dataframe(df5)

        # Provide download button
        csv = df5.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Result CSV",
            data=csv,
            file_name='token.csv',
            mime='text/csv',
        )

    except Exception as e:
        st.error(f"An error occurred during processing: {e}")
