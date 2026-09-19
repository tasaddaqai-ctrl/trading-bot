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
from streamlit_autorefresh import st_autorefresh

# --- UI SETUP ---
st.set_page_config(page_title="AI Quant Explainer", layout="wide", initial_sidebar_state="expanded")
st_autorefresh(interval=60000, limit=None, key="auto_update") # 1 minute refresh

st.markdown("""
<style>
    .big-title {font-size: 34px; font-weight: bold; color: #00F0FF; text-align: center;}
    .explainer-box {background-color: #1E1E1E; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 5px solid #00F0FF;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">🧠 Ultimate Deep Market Explainer</div>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #aaa;">Deep Technical Indicators with Plain Explanations (Auto-Updates every 60s)</p>', unsafe_allow_html=True)

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

# --- DATA FETCHING ---
@st.cache_data(ttl=45)
def fetch_market_data(sym, tf):
    kucoin_tf = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
    try:
        res = requests.get("https://api.kucoin.com/api/v1/market/candles", params={"symbol": sym.replace("USDT", "-USDT"), "type": kucoin_tf.get(tf, "15min")}, timeout=3)
        if res.status_code == 200 and res.json().get('data'):
            df = pd.DataFrame(res.json()['data'], columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='s')
            for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = df[col].astype(float)
            return df.sort_values('timestamp').reset_index(drop=True)
    except: pass
    
    for url in ["https://api.binance.us/api/v3/klines", "https://api.binance.com/api/v3/klines"]:
        try:
            res = requests.get(url, params={"symbol": sym, "interval": tf, "limit": 200}, timeout=3)
            if res.status_code == 200:
                df = pd.DataFrame(res.json(), columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'c', 'q', 'n', 'tb', 'tq', 'i'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = df[col].astype(float)
                return df
        except: continue
    return None

df = fetch_market_data(symbol, timeframe)
if df is None or len(df) < 50:
    st.error("Data Load Error.")
    st.stop()

# --- THE DEEP ALGORITHMS ---
df['EMA_21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()
df['EMA_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
df['EMA_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
macd = MACD(close=df['close'])
df['MACD'] = macd.macd()
df['MACD_Signal'] = macd.macd_signal()
df['MACD_Hist'] = macd.macd_diff()
df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
df['Stoch'] = StochasticOscillator(high=df['high'], low=df['low'], close=df['close']).stoch()
df['ADX'] = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14).adx()
bb = BollingerBands(close=df['close'], window=20, window_dev=2)
df['BB_Mid'] = bb.bollinger_mavg()
df['ATR'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
ichi = IchimokuIndicator(high=df['high'], low=df['low'])
df['Ichi_A'] = ichi.ichimoku_a()
df['Ichi_B'] = ichi.ichimoku_b()

curr = df.iloc[-1]
price = curr['close']

# SCORING (Max 100)
score = 50
if price > curr['EMA_200']: score += 10
else: score -= 10
if curr['MACD'] > curr['MACD_Signal']: score += 10
else: score -= 10
if curr['RSI'] < 35: score += 10 # Oversold bounce
elif curr['RSI'] > 65: score -= 10
if price > curr['BB_Mid']: score += 10
else: score -= 10
if price > curr['Ichi_A'] and price > curr['Ichi_B']: score += 10
elif price < curr['Ichi_A'] and price < curr['Ichi_B']: score -= 10

# Final Signal
signal = "NEUTRAL (Market is Ranging)"
signal_color = "yellow"
if score >= 70 and curr['ADX'] > 20:
    signal = "STRONG BUY 🚀"
    signal_color = "#00FF00"
elif score <= 30 and curr['ADX'] > 20:
    signal = "STRONG SELL 🩸"
    signal_color = "#FF0000"

st.markdown("---")

# --- 1. OVERALL NATEEJA (THE SIGNAL) ---
st.markdown("## 🎯 Overall Nateeja (Final Verdict)")
st.markdown(f"""
<div style="background-color: #111; padding: 25px; border-radius: 12px; border-top: 6px solid {signal_color}; text-align: center;">
    <h1 style="color: {signal_color}; margin: 0;">{signal}</h1>
    <h3 style="color: #fff; margin: 10px 0;">Entry Price: ${price:,.4f}</h3>
</div>
""", unsafe_allow_html=True)
if "BUY" in signal or "SELL" in signal:
    c1, c2 = st.columns(2)
    sl = price - (curr['ATR']*1.5) if "BUY" in signal else price + (curr['ATR']*1.5)
    tp = price + (curr['ATR']*3) if "BUY" in signal else price - (curr['ATR']*3)
    c1.metric("🛡️ Suggest Stop Loss", f"${sl:,.4f}")
    c2.metric("💰 Suggest Take Profit", f"${tp:,.4f}")

st.markdown("---")

# --- 2. DEEP EXPLAINER SECTION ---
st.markdown("## 🧠 Deep Market Explainer (Har Indicator Kya Keh Raha Hai?)")
st.markdown("Market ko practically samjhein ke pichle background mein kia math chal raha hai.")

colA, colB = st.columns(2)

with colA:
    st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
    st.markdown(f"**📈 1. Macro Trend (EMA 200)**<br>Value: ${curr['EMA_200']:,.2f}", unsafe_allow_html=True)
    if price > curr['EMA_200']:
        st.success("**Nateeja:** Price bari Moving Average ke oopar hai. Iska matlab hai Overall bara trend Bullish (Uptrend) hai.")
    else:
        st.error("**Nateeja:** Price bari Moving Average ke neechay hai. Bara trend Bearish (Downtrend) hai.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
    st.markdown(f"**⚡ 2. Momentum (MACD Crossover)**", unsafe_allow_html=True)
    if curr['MACD'] > curr['MACD_Signal']:
        st.success("**Nateeja:** MACD ne neechay se oopar cross kiya hai. Yeh dikhata hai ke kharidne (Buying) walon mein taqat barh rahi hai.")
    else:
        st.error("**Nateeja:** MACD signal line ke neechay hai. Baichne (Selling) walon ka pressure zyada hai.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
    st.markdown(f"**☁️ 3. Ichimoku Cloud (Advance Support/Resistance)**", unsafe_allow_html=True)
    if price > curr['Ichi_A'] and price > curr['Ichi_B']:
        st.success("**Nateeja:** Price Cloud (Baadal) ke oopar trade kar rahi hai. Cloud ab ek mazboot Support ka kaam karega.")
    elif price < curr['Ichi_A'] and price < curr['Ichi_B']:
        st.error("**Nateeja:** Price Cloud ke neechay hai. Market mein bhaari resistance hai, oopar jana mushkil hai.")
    else:
        st.warning("**Nateeja:** Price Cloud ke andar phasi hui hai (No-Trade Zone).")
    st.markdown('</div>', unsafe_allow_html=True)

with colB:
    st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
    st.markdown(f"**⚖️ 4. RSI Condition (Value: {curr['RSI']:.1f})**", unsafe_allow_html=True)
    if curr['RSI'] < 35:
        st.success("**Nateeja:** Market Oversold hai (Zaroorat se zyada gir chuki hai). Yahan se Bounce/Pump aane ka bohat chance hai.")
    elif curr['RSI'] > 65:
        st.error("**Nateeja:** Market Overbought hai (Zaroorat se zyada mehngi ho chuki hai). Yahan se Dump/Giraawat aa sakti hai.")
    else:
        st.info("**Nateeja:** RSI Normal range (40-60) mein hai. Market healthy aur stable hai.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
    st.markdown(f"**🔥 5. ADX Trend Strength (Value: {curr['ADX']:.1f})**", unsafe_allow_html=True)
    if curr['ADX'] > 25:
        st.success("**Nateeja:** Trend mein bohat Taqat (Volume) hai. Jo bhi movement ho rahi hai, wo mazboot hai.")
    else:
        st.warning("**Nateeja:** ADX 25 se kam hai. Trend kamzor hai aur market sirf aik range mein (sideways) time waste kar rahi hai.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
    st.markdown(f"**📏 6. ATR Volatility (Stop-Loss logic)**<br>Value: ${curr['ATR']:,.2f}", unsafe_allow_html=True)
    st.info(f"**Nateeja:** Ek average candle lag bhag ${curr['ATR']:,.2f} ki ban rahi hai. SL aur TP is value ki base par set kiye gaye hain taake market ke shor (noise) se trade hit na ho.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# --- 3. PROFESSIONAL CHART ---
st.markdown("## 📊 Professional Master Chart")
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)

# Main Chart (Candles, EMAs, Ichimoku)
fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'), row=1, col=1)
fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='#FFA500', width=1.5), name='EMA 50'), row=1, col=1)
fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='#FF0055', width=2), name='EMA 200'), row=1, col=1)
fig.add_trace(go.Scatter(x=df['timestamp'], y=df['Ichi_A'], line=dict(color='rgba(0,255,0,0)'), showlegend=False), row=1, col=1)
fig.add_trace(go.Scatter(x=df['timestamp'], y=df['Ichi_B'], line=dict(color='rgba(0,255,0,0)'), fill='tonexty', fillcolor='rgba(0,255,0,0.1)', name='Ichimoku Cloud'), row=1, col=1)

# Oscillators (MACD)
colors = ['#00FF00' if val >= 0 else '#FF0000' for val in df['MACD_Hist']]
fig.add_trace(go.Bar(x=df['timestamp'], y=df['MACD_Hist'], marker_color=colors, name='MACD Hist'), row=2, col=1)
fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MACD'], line=dict(color='#00F0FF', width=1.5), name='MACD'), row=2, col=1)
fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MACD_Signal'], line=dict(color='#FFA500', width=1), name='Signal'), row=2, col=1)

fig.update_layout(template="plotly_dark", height=700, margin=dict(l=0, r=0, t=20, b=0), xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)
