import streamlit as st
import pandas as pd
import requests
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Pro Quant AI", layout="wide", initial_sidebar_state="expanded")
st.title("🚀 Institutional Quant Trading Dashboard")
st.markdown("Yeh dashboard real-time data fetch karta hai aur Institutional concepts par Buy/Sell signals deta hai.")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Engine Parameters")
symbol = st.sidebar.selectbox("Select Asset", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])
timeframe = st.sidebar.selectbox("Primary Timeframe", ["15m", "1h", "4h", "1d"])

# --- DATA FETCHING (Binance API with Fallbacks for Streamlit Cloud) ---
@st.cache_data(ttl=60)
def fetch_binance_data(sym, tf, limit=250):
    # Streamlit Cloud servers are in the US, so we must try multiple API endpoints
    urls = [
        "https://api.binance.us/api/v3/klines",   # Priority 1: Works in US
        "https://api.binance.com/api/v3/klines",  # Priority 2: Global
        "https://api1.binance.com/api/v3/klines"  # Priority 3: Backup
    ]
    params = {"symbol": sym, "interval": tf, "limit": limit}
    
    for url in urls:
        try:
            res = requests.get(url, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 50:
                    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        df[col] = df[col].astype(float)
                    return df
        except:
            continue
    return None # Return None if all APIs fail

@st.cache_data(ttl=3600)
def fetch_fear_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/")
        data = res.json()
        fng_value = data['data'][0]['value']
        fng_class = data['data'][0]['value_classification']
        return int(fng_value), fng_class
    except:
        return 50, "Neutral"

# Fetch Data
with st.spinner("Fetching Live Market Data & Analyzing..."):
    df = fetch_binance_data(symbol, timeframe)
    fng_val, fng_class = fetch_fear_greed()

# Error Handling for US Server Block
if df is None or len(df) < 200:
    st.error("🚨 **Data Fetch Error:** Streamlit Cloud ke US servers ki wajah se Binance API ne filhal data block kar diya hai.")
    st.info("💡 **Hal (Solution):** Is dashboard ko apne PC par locally (`streamlit run dashboard.py`) chalayein. Wahan yeh 100% sahi chalegi kyunke wahan aapka local internet use hota hai jo Binance support karta hai.")
    st.stop()

# --- DEEP TECHNICAL ANALYSIS ---
# Volatility (ATR)
atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14)
df['ATR'] = atr.average_true_range()

# Trend (EMAs)
df['EMA_21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()
df['EMA_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
df['EMA_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()

# Momentum (RSI)
df['RSI_14'] = RSIIndicator(close=df['close'], window=14).rsi()

latest = df.iloc[-1]
prev = df.iloc[-2]
current_price = latest['close']

# --- SIGNAL GENERATION LOGIC ---
signal = "WAIT"
reason = ""
sl = 0
tp = 0

if current_price > latest['EMA_200'] and latest['EMA_21'] > latest['EMA_50'] and latest['RSI_14'] < 70:
    signal = "BUY (LONG)"
    sl = current_price - (latest['ATR'] * 1.5)
    tp = current_price + (latest['ATR'] * 3.0)
    reason = "Strong Macro Uptrend (Price > 200 EMA) + Bullish Momentum."
elif current_price < latest['EMA_200'] and latest['EMA_21'] < latest['EMA_50'] and latest['RSI_14'] > 30:
    signal = "SELL (SHORT)"
    sl = current_price + (latest['ATR'] * 1.5)
    tp = current_price - (latest['ATR'] * 3.0)
    reason = "Strong Macro Downtrend (Price < 200 EMA) + Bearish Momentum."
else:
    reason = "Market is choppy or consolidating. Perfect setup is not formed yet. Protect your capital."

# --- UI LAYOUT ---
col1, col2, col3 = st.columns(3)
col1.metric("Current Price", f"${current_price:,.2f}")
col2.metric("RSI (14) Momentum", f"{latest['RSI_14']:.1f}")
col3.metric("Fundamental Sentiment (Fear/Greed)", f"{fng_val}/100", fng_class)

st.markdown("---")
st.subheader("🤖 AI Trading Signal & Targets")
if signal == "BUY (LONG)":
    st.success(f"**🔥 ACTION:** {signal}")
    st.info(f"**🧠 Logic:** {reason}")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 Entry Price", f"${current_price:,.2f}")
    c2.metric("🛡️ Stop Loss (ATR Dynamic)", f"${sl:,.2f}")
    c3.metric("💰 Take Profit (1:2 RR)", f"${tp:,.2f}")
elif signal == "SELL (SHORT)":
    st.error(f"**🩸 ACTION:** {signal}")
    st.info(f"**🧠 Logic:** {reason}")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 Entry Price", f"${current_price:,.2f}")
    c2.metric("🛡️ Stop Loss (ATR Dynamic)", f"${sl:,.2f}")
    c3.metric("💰 Take Profit (1:2 RR)", f"${tp:,.2f}")
else:
    st.warning(f"**⏳ ACTION:** {signal}")
    st.info(f"**🧠 Logic:** {reason}")

st.markdown("---")
st.subheader("📊 Professional Market View")
fig = go.Figure()
fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price Action'))
fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_21'], line=dict(color='#00F0FF', width=1), name='EMA 21'))
fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='#FFA500', width=1.5), name='EMA 50'))
fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='#FF0055', width=2), name='EMA 200 (Macro)'))
fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=600, margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, use_container_width=True)
st.caption("Developed for Professional Trading. Data sourced dynamically.")
