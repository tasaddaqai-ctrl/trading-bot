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

# --- FETCH ALL COINS DYNAMICALLY ---
@st.cache_data(ttl=86400)
def get_all_usdt_symbols():
    urls = [
        "https://api.binance.us/api/v3/exchangeInfo",
        "https://api.binance.com/api/v3/exchangeInfo",
        "https://api1.binance.com/api/v3/exchangeInfo"
    ]
    for url in urls:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                symbols = [s['symbol'] for s in data['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
                return sorted(symbols)
        except:
            continue
    return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "SHIBUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "MATICUSDT"]

# --- SIDEBAR ---
st.sidebar.header("⚙️ Engine Parameters")
all_symbols = get_all_usdt_symbols()
default_index = all_symbols.index("BTCUSDT") if "BTCUSDT" in all_symbols else 0

symbol = st.sidebar.selectbox("Select Asset", all_symbols, index=default_index)
timeframe = st.sidebar.selectbox("Primary Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=2)

# --- DATA FETCHING (Multi-Exchange Anti-Block System) ---
@st.cache_data(ttl=60)
def fetch_market_data(sym, tf):
    # Priority 1: KuCoin API (Yeh Cloud USA servers par bilkul block nahi hoti)
    kucoin_tf_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
    kucoin_sym = sym.replace("USDT", "-USDT")
    url_kucoin = "https://api.kucoin.com/api/v1/market/candles"
    try:
        res = requests.get(url_kucoin, params={"symbol": kucoin_sym, "type": kucoin_tf_map.get(tf, "15min")}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get('code') == '200000' and data.get('data'):
                # KuCoin columns: timestamp, open, close, high, low, volume, turnover
                df = pd.DataFrame(data['data'], columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='s')
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = df[col].astype(float)
                # Sort from oldest to newest
                df = df.sort_values('timestamp').reset_index(drop=True)
                return df
    except:
        pass
        
    # Priority 2: Binance APIs (Backup)
    urls = [
        "https://api.binance.us/api/v3/klines",
        "https://api.binance.com/api/v3/klines",
        "https://api1.binance.com/api/v3/klines"
    ]
    params = {"symbol": sym, "interval": tf, "limit": 250}
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
    return None

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
    df = fetch_market_data(symbol, timeframe)
    fng_val, fng_class = fetch_fear_greed()

if df is None or len(df) < 50:
    st.error("🚨 **Data Fetch Error:** Streamlit Cloud ke servers API se data nahi nikal pa rahe.")
    st.stop()

# --- DEEP TECHNICAL ANALYSIS ---
atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14)
df['ATR'] = atr.average_true_range()

df['EMA_21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()
df['EMA_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
df['EMA_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
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
st.caption("Developed for Professional Trading. Multi-Exchange Data Sources Active.")
