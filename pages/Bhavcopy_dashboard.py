import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
from nselib import derivatives, capital_market
import plotly.express as px
import logging
import traceback
import yfinance as yf
import concurrent.futures
import pytz

st.set_page_config(layout="wide", page_title="Bhavcopy Dashboard")

st.title("📈 NSE F&O Bhavcopy Dashboard")

# Sidebar inputs
st.sidebar.header("Input Parameters")
stock_list = list(capital_market.fno_equity_list()['symbol'])

selected_value_parameter = st.sidebar.selectbox(
    "Select Metric for Traded Value Calculation",
    options=["Volume", "Open Interest", "Change in OI"]
)
selected_date = st.sidebar.date_input("Select Bhavcopy Date", dt.date.today())
selected_expiry = st.sidebar.date_input("Select Expiry Date", dt.date(2025, 7, 31))
stock_to_track = st.sidebar.selectbox("Stock Symbol for Trend Analysis",options=stock_list)
selected_start_date = st.sidebar.date_input('select start date for trend Analysis')


date_str = selected_date.strftime('%d-%m-%Y')
expiry_str = selected_expiry.strftime('%Y-%m-%d')

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Top 30 by Traded Value ", "📈 Trend Analysis","🔝 Top Traded Option Value"])

with tab1:
    st.subheader(f"Top Stocks by Traded Value on {date_str}")
    
    try:
        data = derivatives.fno_bhav_copy(date_str)
    except Exception as e:
        st.error(f"Failed to fetch bhavcopy: {e}")
        st.stop()
    # Define total_traded_value calculation logic
    def calculate_traded_value(df, method):
        if method == "Volume":
            return df['TtlTradgVol'] * df['NewBrdLotQty'] * df['SttlmPric']
        elif method == "Open Interest":
            return df['OpnIntrst'] * df['SttlmPric']
        elif method == "Change in OI":
            return df['ChngInOpnIntrst'] * df['SttlmPric']
        else:
            return df['TtlTradgVol'] * df['NewBrdLotQty'] * df['SttlmPric']
    
    


    data = data.dropna(subset=['StrkPric', 'OptnTp'])
    data['total_traded_value'] = calculate_traded_value(data, selected_value_parameter)
    data = data[data['XpryDt'] == expiry_str]

    
    #data = data[data['TckrSymb'].isin(stock_list)]

    traded_val_df = data.groupby('TckrSymb')['total_traded_value'].sum().reset_index()
    traded_val_df['total_traded_value'] = traded_val_df['total_traded_value'] / 1e7  # in ₹ Cr
    top_n = traded_val_df.sort_values('total_traded_value', ascending=False).head(30)

    fig_top = px.bar(top_n, x='TckrSymb', y='total_traded_value',
                     title=f'Top 30 Stocks by Total Traded Value - {date_str}',
                     labels={'total_traded_value': '₹ Crores', 'TckrSymb': 'Stock'})
    fig_top.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_top, use_container_width=True)

    st.subheader(" Strike-Wise Total Traded Value")
    
    stock = st.selectbox(
    "Select Stock",
    options=stock_list
)
    
    

    
    stock_df = data[data['TckrSymb'] == stock]
    grouped_df = stock_df.groupby(['StrkPric', 'OptnTp'])['total_traded_value'].sum().reset_index()
    grouped_df['total_traded_value'] = grouped_df['total_traded_value'] / 1e7

    fig = px.bar(grouped_df, x='StrkPric', y='total_traded_value', color='OptnTp',
                 barmode='group', title=f"{stock}: Traded Value by Strike & Type",
                 labels={'StrkPric': 'Strike', 'total_traded_value': '₹ Cr'})
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader(f"Trend Analysis for {stock_to_track}")

    collected_data = []
    strike_data = []
    oi_change_data =[]
    date_range = pd.date_range(start=selected_start_date, end=dt.date.today())
    for date in date_range:
        try:
            d = derivatives.fno_bhav_copy(date.strftime('%d-%m-%Y'))
            daily_cls = d[(d['TckrSymb']==stock_to_track)&(d['XpryDt']==expiry_str)&(d['FinInstrmNm'].str.contains('FUT'))]['ClsPric'].iloc[0]
            d = d.dropna(subset=['StrkPric', 'OptnTp'])
            d = d[(d['TckrSymb'] == stock_to_track) & (d['XpryDt'] == expiry_str)].copy()
            d['total_traded_value'] = calculate_traded_value(d, selected_value_parameter)
            total_val = d['total_traded_value'].sum()
            collected_data.append((date.strftime('%d-%m-%Y'), total_val,daily_cls))
            strike_data.append(d)
            d = d[['StrkPric', 'OptnTp', 'total_traded_value']].copy()
            d['date'] = date.strftime('%Y-%m-%d')
            oi_change_data.append(d)
        except:
            continue

    trend_df = pd.DataFrame(collected_data, columns=['date', 'total_traded_value','daily_close'])
    trend_df['total_traded_value'] = trend_df['total_traded_value'] / 1e7

    if not trend_df.empty:
        fig_trend = px.line(trend_df, x='date', y='total_traded_value',
                            title=f"{stock_to_track} Traded Value & Daily Close Trend",
                            labels={'date': 'Date', 'total_traded_value': '₹ Cr'})

        fig_trend.update_traces(mode='lines+markers', name='Traded Value (₹ Cr)',showlegend=True)

        # Add daily close as a secondary y-axis trace
        fig_trend.add_scatter(x=trend_df['date'],
                            y=trend_df['daily_close'],
                            mode='lines+markers',
                            name='Daily Close',
                            yaxis='y2')

        # Update layout to include secondary y-axis
        fig_trend.update_layout(
            yaxis=dict(title='Traded Value (₹ Cr)'),
            yaxis2=dict(title='Daily Close Price',
                        overlaying='y',
                        side='right'),
            legend=dict(x=0, y=1.1, orientation='h')
        )

        st.plotly_chart(fig_trend, use_container_width=True)

    else:
        st.warning("No data available for trend.")

    if strike_data:
        strike_df = pd.concat(strike_data)
        strike_df['total_traded_value'] = strike_df['total_traded_value'] / 1e7
        strike_df['TradDt'] = pd.to_datetime(strike_df['TradDt'])

        fig_anim = px.bar(strike_df, x='StrkPric', y='total_traded_value', color='OptnTp',
                          animation_frame=strike_df['TradDt'].dt.strftime('%d-%m-%Y'),
                          barmode='group',
                          title=f'{stock_to_track} - Strike vs Traded Value Over Time',
                          labels={'StrkPric': 'Strike', 'total_traded_value': '₹ Cr'})
        st.plotly_chart(fig_anim, use_container_width=True)
    else:
        st.info("No strike-wise data available for animation.")

       
    oi_df = pd.concat(oi_change_data)
    
    # Pivot data: rows = date, columns = (Strike, Option Type), values = OI
    pivoted_oi = oi_df.pivot_table(index='date', columns=['StrkPric', 'OptnTp'], values='total_traded_value')
    pivoted_oi = pivoted_oi.sort_index()

    oi_pct_change = pivoted_oi.pct_change() * 100
    oi_pct_change = oi_pct_change.round(2)

        # Filter for Calls
    calls_change = oi_pct_change.xs('CE', axis=1, level=1, drop_level=False)
    calls_change_T = calls_change.T
    calls_change_T.index = calls_change_T.index.get_level_values(0)  # Extract only StrkPric
    
    fig_calls = px.imshow(
        calls_change_T,
        aspect='auto',
        color_continuous_scale='RdBu',
        zmin=-100, zmax=100,
        labels=dict(x="Date", y="Strike", color="% Change"),
        title=f"{stock_to_track} - % Change in Traded Value (Calls)"
    )
    st.plotly_chart(fig_calls, use_container_width=True)
    # Filter for Puts
    puts_change = oi_pct_change.xs('PE', axis=1, level=1, drop_level=False)
    puts_change_T = puts_change.T
    puts_change_T.index = puts_change_T.index.get_level_values(0)  # Extract only StrkPric
    
    fig_puts = px.imshow(
        puts_change_T,
        aspect='auto',
        color_continuous_scale='RdBu',
        zmin=-100, zmax=100,
        labels=dict(x="Date", y="Strike", color="% Change "),
        title=f"{stock_to_track} - % Change in Traded Value (Puts)"
    )
    st.plotly_chart(fig_puts, use_container_width=True)

with tab3:
    st.subheader("Top 10 Stocks by Traded Value in Calls & Puts (Live Option Chain)")

    def get_ltp(stock):
        try:
            stock_full = stock.upper() + '.NS'
            data = yf.Ticker(stock_full).get_info()
            return data.get('currentPrice') or data.get('regularMarketPrice')
        except Exception as e:
            return None

    def process_stock(stock):
        try:
            ltp = get_ltp(stock)
            if ltp is None:
                return None, None
            data = derivatives.nse_live_option_chain(stock)
            lot_size = data[data['CALLS_Ask_Qty'] != 0]['CALLS_Ask_Qty'].min()
            lot_size = 1 if pd.isna(lot_size) or lot_size == 0 else lot_size
            data['Lot_Size'] = lot_size
            calls = data[data['Strike_Price'] <= ltp].copy()
            puts = data[data['Strike_Price'] >= ltp].copy()
            return calls, puts
        except Exception as e:
            return None, None

    if st.button("Run Live Analysis"):
        with st.spinner("Fetching live option data..."):
            stocks = stock_list
            result_call, result_put = [], []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(process_stock, stocks))
            for calls, puts in results:
                if calls is not None:
                    result_call.append(calls)
                if puts is not None:
                    result_put.append(puts)

            if result_call:
                df_call = pd.concat(result_call)
                df_call['CALLS_Trade_Value'] = df_call['CALLS_Volume'] * df_call['CALLS_LTP'] * df_call['Lot_Size']
                top_calls = df_call.groupby('Symbol')['CALLS_Trade_Value'].sum().sort_values(ascending=False).head(10).reset_index()
                fig_call = px.bar(top_calls, x='Symbol', y='CALLS_Trade_Value',
                                  title='Top 10 Stocks by CALL Traded Value (₹ Cr)',
                                  labels={'CALLS_Trade_Value': '₹ Cr'}, color_discrete_sequence=['green'])
                st.plotly_chart(fig_call, use_container_width=True)

            if result_put:
                df_put = pd.concat(result_put)
                df_put['PUTS_Trade_Value'] = df_put['PUTS_Volume'] * df_put['PUTS_LTP'] * df_put['Lot_Size']
                top_puts = df_put.groupby('Symbol')['PUTS_Trade_Value'].sum().sort_values(ascending=False).head(10).reset_index()
                fig_put = px.bar(top_puts, x='Symbol', y='PUTS_Trade_Value',
                                 title='Top 10 Stocks by PUT Traded Value (₹ Cr)',
                                 labels={'PUTS_Trade_Value': '₹ Cr'}, color_discrete_sequence=['red'])
                st.plotly_chart(fig_put, use_container_width=True)

        ist = pytz.timezone('Asia/Kolkata')
        st.caption(f"Updated at: {pd.Timestamp.now(tz=ist).strftime('%Y-%m-%d %H:%M:%S IST')}")
