import streamlit as st
import pandas as pd
import datetime
import re
import base64
import io
import plotly.express as px
from nselib import derivatives
import pandas_market_calendars as mcal

# Set up the Streamlit app with page configuration
st.set_page_config(page_title="Trading Analysis Dashboard", layout="wide")

# Create a sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Select Page", ["NSE Derivatives Analysis", "POS File Dashboard"])

# Initialize session state variables if they don't exist
if 'm2m' not in st.session_state:
    st.session_state.m2m = None

#########################
# NSE DERIVATIVES PAGE
#########################
def nse_derivatives_page():
    st.title("STOCK CR TOKEN")
    st.write("This app generates stock cr token.")
    
    # Functions for NSE derivatives analysis
    def is_trading_day(date):
        # Get NSE calendar
        nse = mcal.get_calendar('NSE')
        
        # Check if the date is a trading day
        schedule = nse.schedule(start_date=date, end_date=date)
        return not schedule.empty
    
    def run_analysis(date_str, month, oi_threshold, atm_percentage):
        try:
            # Convert date to required format ('DD-MM-YYYY')
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d-%m-%Y')
            
            # Load the derivatives data
            data = derivatives.fno_bhav_copy(formatted_date)
            
            # Check if data is empty
            if data.empty:
                return None, "No data available for the selected date."
            
            # Filter data for rows containing the specified month in 'FinInstrmNm'
            data = data[data['FinInstrmNm'].str.contains(month)].copy()
            
            if data.empty:
                return None, f"No contracts found for {month}."
            
            # Calculate 'open_int' column
            data['open_int'] = data['OpnIntrst'] / data['NewBrdLotQty']
            
            # Filter data for futures contracts containing the specified month followed by 'FUT'
            fut = data[data['FinInstrmNm'].str.contains(f'{month}FUT')].copy()
            FUT = fut['FinInstrmNm'].copy()
            
            # Create a mask for specific conditions
            mask = (
                ((data['StrkPric'] >= data['UndrlygPric']) & (data['OptnTp'] == 'PE')) |
                ((data['StrkPric'] <= data['UndrlygPric']) & (data['OptnTp'] == 'CE'))
            )
            
            # Apply the mask to filter data
            df = data[mask].copy()
            
            if df.empty:
                return None, "No matching data after applying filters."
            
            # Use the user-provided ATM percentage
            atm_decimal = atm_percentage / 100
            
            # Iterate over the DataFrame rows and set 'atm_con' based on conditions with user-defined percentage
            df['atm_con'] = df.apply(
                lambda row: 'True' if (
                    row['StrkPric'] <= row['UndrlygPric'] - (atm_decimal * row['UndrlygPric']) or
                    row['StrkPric'] >= row['UndrlygPric'] + (atm_decimal * row['UndrlygPric'])
                ) else 'False',
                axis=1
            )
            
            # Filter data based on 'atm_con' and 'open_int'
            mask01 = df[df['atm_con'] == "True"]
            mask01 = mask01[mask01['open_int'] > oi_threshold]
            mask02 = df[df['atm_con'] == "False"]
            
            # Merge the filtered data
            df1 = pd.merge(mask01, mask02, how='outer')
            
            if df1.empty:
                return None, "No data after applying OI threshold filter."
            
            # Create a DataFrame with 'FinInstrmNm' column
            df2 = pd.DataFrame(df1['FinInstrmNm'])
            
            # Create 'copy_fin' column with modified values
            df2['copy_fin'] = df2['FinInstrmNm'].str[:-2] + 'PE'
            df2['FinInstrmNm'] = df2['FinInstrmNm'].str[:-2] + 'CE'
            
            # Add 'NRML|' prefix to 'FinInstrmNm' and 'copy_fin'
            df2['FinInstrmNm'] = 'NRML|' + df2['FinInstrmNm']
            df2['copy_fin'] = 'NRML|' + df2['copy_fin']
            
            # FIX FOR FUTURES - Create a DataFrame for futures and rename the column
            if not FUT.empty:
                FUT_df = pd.DataFrame({'fut': 'NRML|' + FUT})
            else:
                FUT_df = pd.DataFrame({'fut': []})
    
            # Prepare final dataframes - First create separate dataframes
            ce_df = pd.DataFrame({'All Columns': df2['FinInstrmNm']})
            pe_df = pd.DataFrame({'All Columns': df2['copy_fin']})
            fut_df = pd.DataFrame({'All Columns': FUT_df['fut']})
            
            # Concatenate all into one dataframe
            df_combined = pd.concat([ce_df, pe_df, fut_df], ignore_index=True)
            
            # Filter out rows containing 'NIFTY'
            df_filtered = df_combined[~df_combined['All Columns'].str.contains('NIFTY', na=False)].copy()
            
            # Initialize a mask with False values
            mask = pd.Series(False, index=df_filtered.index)
            
            # Update the mask if '.' is found in any object type column
            for col in df_filtered.columns:
                if df_filtered[col].dtype == object:
                    mask |= df_filtered[col].str.contains('\.', na=False)
            
            # Filter the DataFrame using the inverted mask
            df5 = df_filtered[~mask]
            
            # Sort the dataframe alphabetically by 'All Columns'
            df5 = df5.sort_values(by='All Columns')
            
            return df5, None
        
        except Exception as e:
            return None, f"Error: {str(e)}"
    
    # Create sidebar for inputs (nested within the NSE page)
    derivatives_sidebar = st.sidebar.expander("Token Parameters", expanded=True)
    
    with derivatives_sidebar:
        # Date picker (default to today)
        today = datetime.date.today()
        date = st.date_input("Select Date", today)
        
        # Month selector
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        current_month_index = datetime.datetime.now().month - 1
        selected_month = st.selectbox("Select Expiry Month", months, index=current_month_index)
        
        # OI threshold
        oi_threshold = st.number_input("OI Threshold", min_value=1, value=4)
        
        # ATM percentage
        atm_percentage = st.slider(
            "ATM Range Percentage", 
            min_value=1, 
            max_value=20, 
            value=8,
            help="Strike prices beyond this percentage from the underlying price will be included based on OI threshold"
        )
        
        # Sort order options
        sort_ascending = st.checkbox("Sort Ascending", value=True, help="Check for ascending order, uncheck for descending")
    
    # Run analysis button
    if st.button("Generate Token"):
        # Check if it's a trading day
        if not is_trading_day(date):
            st.warning(f"Selected date ({date}) may not be a trading day. Results may be unavailable.")
        
        # Convert date to string
        date_str = date.strftime('%Y-%m-%d')
        
        # Display a spinner while processing
        with st.spinner("Processing data..."):
            result_df, error = run_analysis(date_str, selected_month, oi_threshold, atm_percentage)
        
        if error:
            st.error(error)
        else:
            # Apply sorting based on user preference
            result_df = result_df.sort_values(by='All Columns', ascending=sort_ascending)
            
            st.success("Token Generated successfully!")
            
            # Count each type using regex pattern to match at the end of string
            futures_count = result_df['All Columns'].str.contains('FUT$', regex=True).sum()
            ce_count = result_df['All Columns'].str.contains('CE$', regex=True).sum()
            pe_count = result_df['All Columns'].str.contains('PE$', regex=True).sum()
            
            # Display the results
            st.subheader("Show Token")
            st.dataframe(result_df)
            
            # Create download section
            st.subheader("Download Options")
            
            col1, col2 = st.columns(2)
            
            # CSV download in column 1
            with col1:
                csv = result_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"stock_crtoken_{date_str}_{selected_month}.csv",
                    mime="text/csv"
                )
            
            # Text file download in column 2
            with col2:
                # Convert DataFrame to plain text without index
                text_content = "\n".join(result_df['All Columns'].tolist())
                text_bytes = text_content.encode('utf-8')
                
                st.download_button(
                    label="Download TXT",
                    data=text_bytes,
                    file_name=f"stock_crtoken_{date_str}_{selected_month}.txt",
                    mime="text/plain"
                )
            
            # Display additional metrics
            st.subheader("Summary")
            st.write(f"Total tokens: {len(result_df)}")
            st.write(f"- Futures: {futures_count}")
            st.write(f"- Call Options (CE): {ce_count}")
            st.write(f"- Put Options (PE): {pe_count}")
            st.write(f"Analysis parameters: Date={date}, Month={selected_month}, OI Threshold={oi_threshold}, ATM Deviation={atm_percentage}%")
            st.write(f"Sorting: {'Ascending' if sort_ascending else 'Descending'} order")
            
            # Visualize distribution
            st.subheader("Distribution")
            chart_data = pd.DataFrame({
                'Type': ['Futures', 'Call Options', 'Put Options'],
                'Count': [futures_count, ce_count, pe_count]
            })
            st.bar_chart(chart_data.set_index('Type'))
    
    # Add explanatory information
    with st.expander("About Stock CR Token "):
        st.info(f"""
        This tool retrieves NSE derivatives data for a selected date and applies filters based on:
        - Selected month
        - Open Interest threshold
        - ATM conditions (user-defined deviation from underlying price)
        - PE/CE conditions
        
        The result is a list of derivative tokens for trading strategies, including futures contracts.
        """)
        
        st.subheader("How ATM Range Percentage")
        st.info(f"""
        The ATM (At-The-Money) range percentage defines how far away from the underlying price a strike will be included in token without considering the OI beyond this only strike with OI equal or greater than the threshold will be included in the token:
        
        - For a {atm_percentage}% setting, strikes that are more than {atm_percentage}% above or below the underlying price will be filtered based on OI.
        - Lower percentage = stricter filtering (closer to the money)
        - Higher percentage = looser filtering (includes strikes further from the money)
        
        
        """)

#########################
# POS FILE DASHBOARD PAGE
#########################
def pos_file_dashboard():
    st.title("POSITION MATCHING")
    st.header("Upload POS File (Excel)")
    
    # Function to process the data
    def parse_pos_contents(file):
        try:
            df = pd.read_excel(uploaded_file)
            st.success(f"Successfully read POS file")
            
            # First, display the first few rows to help debugging
            with st.expander("Data Preview (First 5 Rows)"):
                st.dataframe(df.head())
            
            # Display column names to help with debugging
            with st.expander("Column Names"):
                st.write(df.columns.tolist())
            
            # Data cleaning and processing steps for POS file
            # More robust approach to find rows with CE, PE, FX
            new_data = []
            for index, row in df.iterrows():
                if any(keyword in row.values for keyword in ['CE', 'PE', 'FX']):
                    new_data.append(row)
            
            if not new_data:
                st.warning("No rows found containing 'CE', 'PE', or 'FX'. Please check your file format.")
                return None, None, None, None, None, None
            
            new_data = pd.DataFrame(new_data)
            new_data.dropna(axis=1, inplace=True)
            new_data.reset_index(drop=True, inplace=True)
            
            # Display processed data preview for debugging
            with st.expander("Processed Data Preview"):
                st.dataframe(new_data.head())
                st.write("Processed data columns:", new_data.columns.tolist())
            
            # Calculate exposure and other sums using identified columns
            try:
                 # Calculate exposure and other sums
                exp = new_data[new_data['Unnamed: 7'] == 'FX']['Unnamed: 15'].sum()
                exp = exp/100000
                exp = round(exp)
                exposure = f'{exp} Lac'
                fx_sum = new_data[new_data['Unnamed: 7'] == 'FX']['Unnamed: 9'].sum()
                ce_sum = new_data[new_data['Unnamed: 7'] == 'CE']['Unnamed: 9'].sum()
                pe_sum = new_data[new_data['Unnamed: 7'] == 'PE']['Unnamed: 9'].sum()
                if abs(fx_sum) == abs(ce_sum) == abs(pe_sum):
                    position = 'Matched'
                else:
                    position = 'Not Matched'

                return new_data, exposure, fx_sum, ce_sum, pe_sum, position
                
            except Exception as e:
                st.error(f"Error in calculations: {str(e)}")
                return None, None, None, None, None, None, None, None
        
        except Exception as e:
            st.error(f"Error parsing POS file: {str(e)}")
            return None, None, None, None, None, None, None, None
    
    # File uploader
    uploaded_file = st.file_uploader("Drag and Drop or Select POS File", type=["xls", "xlsx"])
    
    # Process uploaded file
    if uploaded_file is not None:
        results = parse_pos_contents(uploaded_file)
        
        if results is not None and len(results) >= 6:
            pos_data, exposure, fx_sum, ce_sum, pe_sum, position = results[:6]
            stock_column = results[6] if len(results) > 6 else None
            m2m_column = results[7] if len(results) > 7 else None
            
            if pos_data is not None:
                # Store data in session state
                st.session_state.m2m = pos_data
                
                # Display info in expander
                with st.expander("View Summary Information", expanded=True):
                    st.write(f"Total Exposure: {exposure}")
                    st.write(f"Sum for FX: {fx_sum}")
                    st.write(f"Sum for CE: {ce_sum}")
                    st.write(f"Sum for PE: {pe_sum}")
                    st.write(f"Position: {position}")
                
                # Create and display the bar chart
                try:
                    filtered_data = pos_data[pos_data['Unnamed: 7'] == 'FX'].sort_values(by=['Unnamed: 17'])
                    filtered_data = filtered_data[filtered_data['Unnamed: 9'] != 0]    
                    if not filtered_data.empty:
                        fig = px.bar(filtered_data, x="Unnamed: 0", y="Unnamed: 17",labels={'Unnamed: 0': 'Stocks', 'Unnamed: 17': 'M2M'},title="M2M")  # Create the plot
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No data available for plotting after filtering.")
                except Exception as plot_error:
                    st.error(f"Error creating plot: {str(plot_error)}")
                
                # Display raw data table
                with st.expander("View Raw Data", expanded=False):
                    st.dataframe(pos_data)
            else:
                st.error("Error processing POS file data.")
        else:
            st.error("Incomplete results from data processing.")
    else:
        st.info("Please upload the POS Excel file.")

# Main app logic - Display the selected page
if page == "NSE Derivatives Analysis":
    nse_derivatives_page()
else:
    pos_file_dashboard()

# Add Footer
st.markdown("---")
st.markdown("Trading Analysis Dashboard | Created with Streamlit")