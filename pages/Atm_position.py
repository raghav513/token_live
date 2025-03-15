import pandas as pd
import streamlit as st
import openpyxl

# Only include title and header once
st.title("AT Money Position")
st.header("Upload POS File (Excel)")

# Add a slider for ATM range selection
atm_range = st.slider("Select ATM Range (±)", 
                      min_value=1, 
                      max_value=20, 
                      value=5,
                      help="Options with strike prices within this range of the future's LTP will be considered ATM")

def parse_pos_contents(file, atm_range_value):
    try:
        # Read the uploaded file
        data = pd.read_excel(file, header=1, index_col=0)
        st.success("Successfully read POS file!")

        # Ensure required columns exist
        required_columns = {'Call/Put', 'Scrip', 'STK', 'LTP', 'BF Qty'}
        if not required_columns.issubset(data.columns):
            st.error(f"Missing required columns: {required_columns - set(data.columns)}")
            return None

        # Filter out rows where BF Qty is 0
        data = data[data['BF Qty'] != 0]
        
        # Separate Futures and Options
        fut = data[data['Call/Put'] == 'FF']
        opt = data[data['Call/Put'] != 'FF']

        # Create an empty DataFrame for ATM options
        ATM = pd.DataFrame(columns=opt.columns)

        # Iterate through options data
        for index, row in opt.iterrows():
            # Find matching Future contract
            matching_fut = fut[fut['Scrip'] == row['Scrip']]
            if not matching_fut.empty:
                ltp_value = matching_fut['LTP'].values[0]  # Get the first matching LTP value

                # Check if option is At The Money (using the user-selected range)
                if abs(row['STK'] - ltp_value) < atm_range_value:
                    if row['STK'] < ltp_value and row['Call/Put']=='CE' or row['STK'] > ltp_value and row['Call/Put']=='PE':
                        ATM = pd.concat([ATM, pd.DataFrame([row.values], columns=ATM.columns)], ignore_index=True)

        # Display ATM data
        if not ATM.empty:
            ATM = ATM[['Scrip', 'Call/Put', 'Exp Date', 'STK', 'BF Qty']]
            with st.expander("At Money Position", expanded=True):
                st.dataframe(ATM)
                
                # Add download button for the ATM data
                csv = ATM.to_csv().encode('utf-8')
                st.download_button(
                    label="Download ATM Data as CSV",
                    data=csv,
                    file_name="atm_positions.csv",
                    mime="text/csv",
                )
        else:
            st.warning(f"No ATM options found within ±{atm_range_value} of future price.")

    except Exception as e:
        st.error(f"Error parsing POS file: {str(e)}")
        return None

# File uploader with a unique key
uploaded_file = st.file_uploader("Drag and Drop or Select POS File", 
                                type=["xls", "xlsx", 'csv'],
                                key="pos_file_uploader")

# Process the file only if it is uploaded
if uploaded_file is not None:
    parse_pos_contents(uploaded_file, atm_range)
else:
    st.info("Please upload a POS Excel file.")

