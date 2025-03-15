import streamlit as st
import pandas as pd
import plotly.express as px







st.title("POSITION MATCHING")
st.header("Upload POS File (Excel)")
    
    # Function to process the data
def parse_pos_contents(file):
    try:
        df = pd.read_excel(uploaded_file)
        st.success(f"Successfully read POS file")
            
       
        
            
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
uploaded_file = st.file_uploader("Drag and Drop or Select POS File", type=["xls", "xlsx", 'csv'])

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

            if position == "Matched":
                position_text = '<span style="color:green; font-weight:bold;">Matched</span>'
            else:
                position_text = '<span style="color:red; font-weight:bold;">Not Matched</span>'

            
            # Display info in expander
            with st.expander("View Summary Information", expanded=True):
                st.write(f"Total Exposure: {exposure}")
                st.write(f"Sum for FX: {fx_sum}")
                st.write(f"Sum for CE: {ce_sum}")
                st.write(f"Sum for PE: {pe_sum}")
                st.markdown(f"**Position:** {position_text}",unsafe_allow_html=True)
            
            # Create and display the bar chart
            try:
                filtered_data = pos_data[pos_data['Unnamed: 7'] == 'FX'].sort_values(by=['Unnamed: 17'])
                filtered_data = filtered_data[filtered_data['Unnamed: 9'] != 0]   
                if not filtered_data.empty:
                    fig = px.bar(filtered_data, x="Unnamed: 0", y="Unnamed: 17",labels={'Unnamed: 0': 'Stocks', 'Unnamed: 17': 'M2M'},title="M2M")  # Create the plot
                    fig.update_layout(xaxis_tickangle=-90)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No data available for plotting after filtering.")
            except Exception as plot_error:
                st.error(f"Error creating plot: {str(plot_error)}")
            
            # Display raw data table
            with st.expander("View Raw Data", expanded=False):
                st.dataframe(pos_data)

            if position == 'Not Matched':
                # Get unique stock names
                data = pos_data
                stock_list = data['Unnamed: 0'].unique()
                mismatch_strikes = []
                Future_mismatch =[]

                # Filter CE and PE data first
                data_ce_pe = data[data['Unnamed: 7'].isin(['CE', 'PE'])]
                data_fx = data[data['Unnamed: 7'] == 'FX']

                # Loop through each stock
                for stock in stock_list:
                    stock_data = data_ce_pe[data_ce_pe['Unnamed: 0'] == stock]  # Filter for current stock
                    stock_data_fx = data_fx[data_fx['Unnamed: 0'] == stock]

                    # Get total FX quantity for this stock
                    fx_quantity = stock_data_fx['Unnamed: 9'].sum() if not stock_data_fx.empty else 0

                    # Get total CE sum for the current stock
                    ce_sum = stock_data[stock_data['Unnamed: 7'] == 'CE']['Unnamed: 9'].sum()

                    # If CE and FX do not balance out, store the mismatch
                    

                    # Iterate over each strike price
                    for strike, group in stock_data.groupby('COMBINED NET POSITION'):  # Assuming 'Unnamed: 3' is the strike column
                        ce_quantity = group[group['Unnamed: 7'] == 'CE']['Unnamed: 9'].sum()
                        pe_quantity = group[group['Unnamed: 7'] == 'PE']['Unnamed: 9'].sum()

                        # If CE and PE do not balance out, store the mismatch
                        if ce_quantity + pe_quantity != 0:
                            mismatch_strikes.append((stock, strike, ce_quantity, pe_quantity, fx_quantity))
                        else:
                            if ce_sum + fx_quantity != 0:
                                Future_mismatch.append((stock, fx_quantity,ce_sum))

                # Convert to DataFrame
                mismatch_strikes_df = pd.DataFrame(mismatch_strikes, columns=['Stock', 'Strike', 'CE Quantity', 'PE Quantity', 'FX Quantity'])
                Future_mismatch_df = pd.DataFrame(Future_mismatch,columns=['stock','net fx quantity', 'net ce quantity'])
                with st.expander("Mis-Match in CE, PE", expanded=True):
                    st.dataframe(data=mismatch_strikes_df)
                with st.expander("Mis-Match in FX", expanded=True):
                    st.dataframe(data=Future_mismatch_df)
            else:
                st.text('NO Mis-Match Data')
        else:
            st.error("Error processing POS file data.")
    else:
        st.error("Incomplete results from data processing.")
else:
    st.info("Please upload the POS Excel file.")

