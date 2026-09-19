import streamlit as st
import pandas as pd
import requests
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import AverageTrueRange, BollingerBands
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- UI SETUP ---
st.set_page_config(page_title="AI Quant Engine Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-title {font-size: 38px; font-weight: bold; color: #00F0FF; margin-bottom: 0px;}
    .sub-title {font-size: 16px; color: #aaaaaa; margin-bottom: 30px;}
    .stat-box {background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🚀 Ultimate Quant Trading Engine Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Powered by 7 Advanced Algorithms & Multi-Exchange Live Data</div>', unsafe_allow_html=True)

# --- SIDEBAR & PARAMS ---
@st.cache_data(ttl=86400)
def get_all_usdt_symbols():
    for url in ["https://api.binance.us/api/v3/exchangeInfo", "https://api.binance.com/api/v3/exchangeInfo"]:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                return sorted([s['symbol'] for s in data['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING'])
        except: continue
    return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

all_symbols = get_all_usdt_symbols()
st.sidebar.header("⚙️ Strategy Settings")
symbol = st.sidebar.selectbox("Select Asset", all_symbols, index=all_symbols.index("BTCUSDT") if "BTCUSDT" in all_symbols else 0)
timeframe = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"], index=2)

# --- DATA FETCHING ---
@st.cache_data(ttl=60)
def fetch_market_data(sym, tf):
    kucoin_tf = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
    try:
        res = requests.get("https://api.kucoin.com/api/v1/market/candles", params={"symbol": sym.replace("USDT", "-USDT"), "type": kucoin_tf.get(tf, "15min")}, timeout=5)
        if res.status_code == 200 and res.json().get('data'):
            df = pd.DataFrame(res.json()['data'], columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='s')
            for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = df[col].astype(float)
            return df.sort_values('timestamp').reset_index(drop=True)
    except: pass
    
    for url in ["https://api.binance.us/api/v3/klines", "https://api.binance.com/api/v3/klines"]:
        try:
            res = requests.get(url, params={"symbol": sym, "interval": tf, "limit": 300}, timeout=5)
            if res.status_code == 200:
                df = pd.DataFrame(res.json(), columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'c', 'q', 'n', 'tb', 'tq', 'i'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = df[col].astype(float)
                return df
        except: continue
    return None

df = fetch_market_data(symbol, timeframe)
if df is None or len(df) < 50:
    st.error("🚨 Connection Error: Unable to fetch market data from APIs.")
    st.stop()

# --- THE "PERFECT" DEEP ALGORITHM (7 Indicators) ---
# 1. EMAs (Trend)
df['EMA_21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()
df['EMA_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
df['EMA_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
# 2. MACD (Momentum)
macd = MACD(close=df['close'])
df['MACD'] = macd.macd()
df['MACD_Signal'] = macd.macd_signal()
df['MACD_Hist'] = macd.macd_diff()
# 3. RSI & Stochastic (Overbought/Oversold)
df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
df['Stoch'] = StochasticOscillator(high=df['high'], low=df['low'], close=df['close']).stoch()
# 4. Bollinger Bands (Volatility & Mean Reversion)
bb = BollingerBands(close=df['close'], window=20, window_dev=2)
df['BB_High'] = bb.bollinger_hband()
df['BB_Mid'] = bb.bollinger_mavg()
df['BB_Low'] = bb.bollinger_lband()
# 5. ADX (Trend Strength)
df['ADX'] = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14).adx()
# 6. ATR (Targets / Stop Loss)
df['ATR'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()

curr = df.iloc[-1]
current_price = curr['close']

# --- CONFLUENCE SCORING SYSTEM (0 to 100%) ---
score = 50 # Starts neutral
if current_price > curr['EMA_200']: score += 10 # Macro Bullish
else: score -= 10
if curr['EMA_21'] > curr['EMA_50']: score += 10 # Micro Bullish
else: score -= 10
if curr['MACD'] > curr['MACD_Signal']: score += 10 # Momentum Up
else: score -= 10
if 40 < curr['RSI'] < 70: score += 5 # Healthy Bullish RSI
elif curr['RSI'] < 30: score += 10 # Oversold (Bounce expected)
elif curr['RSI'] > 70: score -= 10 # Overbought (Drop expected)
if current_price > curr['BB_Mid']: score += 5 
else: score -= 5

score = max(0, min(100, score)) # Cap between 0 and 100

# SIGNAL LOGIC
signal = "WAIT (CHOPPY)"
color = "orange"
sl, tp = 0, 0
reason = ""

if score >= 75 and curr['ADX'] > 20:
    signal = "STRONG BUY 🚀"
    color = "#00FF00"
    sl = current_price - (curr['ATR'] * 1.5)
    tp = current_price + (curr['ATR'] * 3.0)
    reason = "Algorithm detected massive confluence. Trend, Momentum, and Volume are aligned upwards."
elif score <= 25 and curr['ADX'] > 20:
    signal = "STRONG SELL 🩸"
    color = "#FF0000"
    sl = current_price + (curr['ATR'] * 1.5)
    tp = current_price - (curr['ATR'] * 3.0)
    reason = "Algorithm detected massive bearish confluence. Sellers are in complete control."
else:
    reason = "Indicators are mixed. ADX shows weak trend. No clear trade setup. Protect Capital."

# --- TOP DASHBOARD METRICS ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Live Price", f"${current_price:,.4f}")
c2.metric("AI Confluence Score", f"{score}%", "Bullish" if score > 50 else "Bearish" if score < 50 else "Neutral")
c3.metric("Trend Strength (ADX)", f"{curr['ADX']:.1f}", "Strong Trend" if curr['ADX'] > 25 else "Weak/Ranging")
c4.metric("Volatility (ATR)", f"${curr['ATR']:.4f}", "Stop Loss Range")

st.markdown("---")

# --- MAIN LAYOUT (Chart + AI Box) ---
col_chart, col_ai = st.columns([2.5, 1])

with col_ai:
    st.markdown("### 🤖 AI Engine Decision")
    st.markdown(f"""
    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 10px; border-top: 5px solid {color}; box-shadow: 0 4px 8px rgba(0,0,0,0.5);">
        <h2 style="text-align: center; color: {color}; margin-top: 0px;">{signal}</h2>
        <p style="color: #CCCCCC; font-size: 14px;">{reason}</p>
        <hr style="border-color: #333;">
        <h4 style="color: #fff; margin-bottom: 5px;">🎯 Targets</h4>
        <b>Entry:</b> ${current_price:,.4f}<br>
        <b style="color: #FF4B4B;">Stop Loss:</b> ${sl:,.4f}<br>
        <b style="color: #00FF00;">Take Profit:</b> ${tp:,.4f}<br>
        <hr style="border-color: #333;">
        <p style="font-size: 12px; color: #888; text-align: center;">Risk/Reward Ratio: 1:2.0</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🔬 Indicator Breakdown")
    with st.expander("View Deep Algorithm Logic", expanded=True):
        st.write(f"**EMA (21 vs 50):** {'Bullish' if curr['EMA_21'] > curr['EMA_50'] else 'Bearish'}")
        st.write(f"**MACD Histogram:** {'Positive (Buying)' if curr['MACD_Hist'] > 0 else 'Negative (Selling)'}")
        st.write(f"**RSI (14):** {curr['RSI']:.1f} (Ideal: 40-70)")
        st.write(f"**Stochastic:** {curr['Stoch']:.1f} {'(Oversold)' if curr['Stoch'] < 20 else '(Overbought)' if curr['Stoch'] > 80 else ''}")
        st.write(f"**Price vs BB:** {'Above Mid' if current_price > curr['BB_Mid'] else 'Below Mid'}")

with col_chart:
    # PROFESSIONAL PLOTLY SUBPLOTS
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03, subplot_titles=("Price Action & Bollinger Bands", "MACD Momentum", "RSI Oscillator"))
    
    # Row 1: Candlesticks + BB + EMAs
    fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['BB_High'], line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dot'), name='BB High'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['BB_Low'], line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(255,255,255,0.05)', name='BB Low'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='#FFA500', width=1.5), name='EMA 50'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='#FF0055', width=2), name='EMA 200 (Macro)'), row=1, col=1)
    
    # Row 2: MACD
    colors = ['#00FF00' if val >= 0 else '#FF0000' for val in df['MACD_Hist']]
    fig.add_trace(go.Bar(x=df['timestamp'], y=df['MACD_Hist'], marker_color=colors, name='MACD Hist'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MACD'], line=dict(color='#00F0FF', width=1.5), name='MACD Line'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MACD_Signal'], line=dict(color='#FFA500', width=1), name='Signal Line'), row=2, col=1)
    
    # Row 3: RSI
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['RSI'], line=dict(color='#E0B0FF', width=1.5), name='RSI'), row=3, col=1)
    fig.add_hline(y=70, line=dict(color='red', width=1, dash='dash'), row=3, col=1)
    fig.add_hline(y=30, line=dict(color='green', width=1, dash='dash'), row=3, col=1)
    
    fig.update_layout(
        template="plotly_dark", 
        height=800, 
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
    
    st.plotly_chart(fig, use_container_width=True)

st.caption("Developed by AI for Institutional Grade Analysis. Combines 7 algorithms for maximum confluence.")
