import streamlit as st
import pandas as pd
import requests
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator, IchimokuIndicator
from ta.volatility import AverageTrueRange, BollingerBands
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from textblob import TextBlob
from datetime import datetime

# --- UI SETUP ---
st.set_page_config(page_title="Ultimate Trading Pro", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .big-title {font-size: 38px; font-weight: bold; color: #00F0FF; text-align: center;}
    .sub-text {font-size: 16px; color: #aaaaaa; text-align: center; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">🤖 Ultimate Master Trading Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Perfect Technical + Fundamental Analysis In One Place</div>', unsafe_allow_html=True)

# --- SELECTORS ---
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
col1, col2 = st.columns(2)
symbol = col1.selectbox("🪙 Select Coin", all_symbols, index=all_symbols.index("BTCUSDT") if "BTCUSDT" in all_symbols else 0)
timeframe = col2.selectbox("⏱️ Timeframe", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"], index=2)

# --- DATA FETCHING (Tech + Fundamentals) ---
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

@st.cache_data(ttl=300)
def fetch_fundamental_data(sym):
    funds = {'fng_value': 50, 'fng_class': 'Neutral', 'news_score': 0, 'news_list': []}
    # 1. Fear and Greed Index
    try:
        f_res = requests.get("https://api.alternative.me/fng/", timeout=5).json()
        funds['fng_value'] = int(f_res['data'][0]['value'])
        funds['fng_class'] = f_res['data'][0]['value_classification']
    except: pass
    
    # 2. Live Crypto News Sentiment (NLP)
    try:
        n_res = requests.get("https://min-api.cryptocompare.com/data/v2/news/?lang=EN", timeout=5).json()
        news_items = n_res.get('Data', [])[:10]
        score = 0
        for n in news_items:
            title = n.get('title', '')
            blob = TextBlob(title)
            polarity = blob.sentiment.polarity
            score += polarity
            funds['news_list'].append({
                "title": title, 
                "sentiment": "🟢 Bullish" if polarity > 0 else "🔴 Bearish" if polarity < 0 else "⚪ Neutral", 
                "url": n.get('url')
            })
        if len(news_items) > 0:
            funds['news_score'] = score / len(news_items)
    except: pass
    return funds

with st.spinner("Deep Algorithmic & Fundamental Analysis Loading..."):
    df = fetch_market_data(symbol, timeframe)
    funds = fetch_fundamental_data(symbol)

if df is None or len(df) < 50:
    st.error("🚨 Connection Error: Data nahi mil raha.")
    st.stop()

# --- THE "PERFECT" TECHNICAL ALGORITHMS ---
# EMAs
df['EMA_21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()
df['EMA_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
df['EMA_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
# MACD
macd = MACD(close=df['close'])
df['MACD'] = macd.macd()
df['MACD_Signal'] = macd.macd_signal()
df['MACD_Hist'] = macd.macd_diff()
# Oscillators
df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
df['Stoch'] = StochasticOscillator(high=df['high'], low=df['low'], close=df['close']).stoch()
# Volatility
bb = BollingerBands(close=df['close'], window=20, window_dev=2)
df['BB_High'] = bb.bollinger_hband()
df['BB_Mid'] = bb.bollinger_mavg()
df['BB_Low'] = bb.bollinger_lband()
df['ATR'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
# Trend Strength
df['ADX'] = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14).adx()
# Advanced: Ichimoku Cloud
ichi = IchimokuIndicator(high=df['high'], low=df['low'])
df['Ichi_A'] = ichi.ichimoku_a()
df['Ichi_B'] = ichi.ichimoku_b()
# Advanced: Fibonacci Retracement Levels
max_price = df['high'].max()
min_price = df['low'].min()
diff = max_price - min_price
fib_levels = {
    "Fib 0.0 (High)": max_price,
    "Fib 0.236": max_price - 0.236 * diff,
    "Fib 0.382": max_price - 0.382 * diff,
    "Fib 0.500": max_price - 0.5 * diff,
    "Fib 0.618": max_price - 0.618 * diff,
    "Fib 1.0 (Low)": min_price
}

curr = df.iloc[-1]
current_price = curr['close']

# --- MASTER CONFLUENCE ENGINE (70% Tech + 30% Funda) ---
tech_score = 50
if current_price > curr['EMA_200']: tech_score += 10
else: tech_score -= 10
if curr['EMA_21'] > curr['EMA_50']: tech_score += 10
else: tech_score -= 10
if curr['MACD'] > curr['MACD_Signal']: tech_score += 10
else: tech_score -= 10
if 40 < curr['RSI'] < 70: tech_score += 5
elif curr['RSI'] < 30: tech_score += 10
elif curr['RSI'] > 70: tech_score -= 10
if current_price > curr['BB_Mid']: tech_score += 5 
else: tech_score -= 5

funda_score = 50
if funds['fng_value'] > 60: funda_score += 10
elif funds['fng_value'] < 40: funda_score -= 10
if funds['news_score'] > 0.1: funda_score += 20
elif funds['news_score'] < -0.1: funda_score -= 20

total_master_score = (tech_score * 0.7) + (funda_score * 0.3)
total_master_score = max(0, min(100, total_master_score))

# --- SIGNAL GENERATOR ---
signal = "WAIT (Neutral)"
sl, tp = 0, 0
logic_msg = "Market abhi kisi wazeh trend mein nahi hai. Fundamental aur Technical data aapas mein takra raha hai."

if total_master_score >= 65 and curr['ADX'] > 20:
    signal = "STRONG BUY 🚀"
    sl = current_price - (curr['ATR'] * 1.5)
    tp = current_price + (curr['ATR'] * 3.0)
    logic_msg = "PERFECT SETUP: Fundamentals (News/Sentiment) aur Technicals (Trend/Momentum) dono 100% Bullish hain!"
elif total_master_score <= 35 and curr['ADX'] > 20:
    signal = "STRONG SELL 🩸"
    sl = current_price + (curr['ATR'] * 1.5)
    tp = current_price - (curr['ATR'] * 3.0)
    logic_msg = "PERFECT SETUP: Fundamentals aur Technicals dono Bearish hain. Sellers ka poora control hai."

st.markdown("---")

# --- MASTER SIGNAL UI ---
st.markdown("<h3 style='text-align: center;'>🎯 The Perfect Master Signal</h3>", unsafe_allow_html=True)
if "BUY" in signal:
    st.success(f"### 🟢 ACTION: {signal}\n{logic_msg}")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 Entry", f"${current_price:,.4f}")
    c2.metric("💰 Take Profit", f"${tp:,.4f}")
    c3.metric("🛡️ Stop Loss", f"${sl:,.4f}")
elif "SELL" in signal:
    st.error(f"### 🔴 ACTION: {signal}\n{logic_msg}")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 Entry", f"${current_price:,.4f}")
    c2.metric("💰 Take Profit", f"${tp:,.4f}")
    c3.metric("🛡️ Stop Loss", f"${sl:,.4f}")
else:
    st.warning(f"### 🟡 ACTION: {signal}\n{logic_msg}")

st.markdown("---")

# --- TABS FOR EVERYTHING ---
tab1, tab2, tab3 = st.tabs(["🌍 Perfect Fundamentals", "📈 Ultimate Technicals", "📊 Master Chart"])

with tab1:
    st.markdown("### 📰 Fundamental Analysis & Global Sentiment")
    colA, colB = st.columns(2)
    with colA:
        st.markdown(f"**🧠 Fear & Greed Index:** {funds['fng_value']}/100 ({funds['fng_class']})")
        st.progress(funds['fng_value'] / 100.0)
        st.markdown("*Market ki overall Psychology. (High Greed = Risky, High Fear = Opportunity)*")
    with colB:
        sentiment_word = "Bullish (Positive)" if funds['news_score'] > 0.05 else "Bearish (Negative)" if funds['news_score'] < -0.05 else "Neutral"
        st.markdown(f"**📰 AI News Sentiment Score:** {funds['news_score']:.2f}")
        st.markdown(f"**Overall News Impact:** :blue[{sentiment_word}]")
    
    st.markdown("#### 📡 Live Breaking News (AI Evaluated)")
    for n in funds['latest_news'] if 'latest_news' in funds else funds['news_list']:
        st.write(f"- {n['sentiment']} | [{n['title']}]({n['url']})")

with tab2:
    st.markdown("### 🧮 The 7 Algorithm Breakdown")
    c1, c2 = st.columns(2)
    c1.write(f"**1. Macro Trend (EMA 200):** {'🟢 Bullish' if current_price > curr['EMA_200'] else '🔴 Bearish'}")
    c1.write(f"**2. Micro Trend (EMA 21/50):** {'🟢 Bullish' if curr['EMA_21'] > curr['EMA_50'] else '🔴 Bearish'}")
    c1.write(f"**3. Momentum (MACD):** {'🟢 Bullish' if curr['MACD_Hist'] > 0 else '🔴 Bearish'}")
    c1.write(f"**4. Trend Strength (ADX):** {'🔥 Strong' if curr['ADX'] > 25 else '❄️ Weak/Ranging'}")
    
    c2.write(f"**5. Market Condition (RSI):** {curr['RSI']:.1f} {'(🟢 Optimal)' if 40 < curr['RSI'] < 70 else '(🔴 Extreme)'}")
    c2.write(f"**6. Speed (Stoch):** {curr['Stoch']:.1f} {'(🟢 Oversold)' if curr['Stoch'] < 20 else '(🔴 Overbought)' if curr['Stoch'] > 80 else ''}")
    c2.write(f"**7. Volatility (Bollinger):** {'🟢 Above Mid' if current_price > curr['BB_Mid'] else '🔴 Below Mid'}")
    
    st.markdown("#### 📐 Fibonacci Retracement (Auto Support & Resistance)")
    for level, price in fib_levels.items():
        st.write(f"- **{level}:** ${price:,.2f}")

with tab3:
    st.markdown("### 📊 Advanced Interactive Chart (Ichimoku + MACD)")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    # Candlestick + Ichimoku Cloud (Highly Advanced Indicator)
    fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'), row=1, col=1)
    
    # Ichimoku Cloud Fill
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['Ichi_A'], line=dict(color='rgba(0,255,0,0)'), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['Ichi_B'], line=dict(color='rgba(0,255,0,0)'), fill='tonexty', fillcolor='rgba(0,255,0,0.1)', name='Ichimoku Cloud'), row=1, col=1)
    
    # MACD
    colors = ['#00FF00' if val >= 0 else '#FF0000' for val in df['MACD_Hist']]
    fig.add_trace(go.Bar(x=df['timestamp'], y=df['MACD_Hist'], marker_color=colors, name='MACD Hist'), row=2, col=1)
    
    fig.update_layout(template="plotly_dark", height=600, margin=dict(l=0, r=0, t=10, b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
