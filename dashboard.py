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
st_autorefresh(interval=60000, limit=None, key="auto_update")

st.markdown("""
<style>
    .big-title {font-size: 34px; font-weight: bold; color: #00F0FF; text-align: center;}
    .explainer-box {background-color: #1E1E1E; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 5px solid #00F0FF;}
    .fund-box {background-color: #1E1E1E; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 5px solid #FFA500;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">🧠 Ultimate Deep Market Explainer</div>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #aaa;">Deep Technical & Fundamental Indicators (Updates every 60s)</p>', unsafe_allow_html=True)

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

@st.cache_data(ttl=300)
def fetch_fundamental_data(sym):
    funds = {'fng_value': 50, 'fng_class': 'Neutral', 'news_score': 0, 'news_list': []}
    # 1. Fear and Greed Index
    try:
        f_res = requests.get("https://api.alternative.me/fng/", timeout=5).json()
        funds['fng_value'] = int(f_res['data'][0]['value'])
        funds['fng_class'] = f_res['data'][0]['value_classification']
    except: pass
    # 2. Live News Sentiment via TextBlob NLP
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
                "sentiment": "🟢 Bullish" if polarity > 0.1 else "🔴 Bearish" if polarity < -0.1 else "⚪ Neutral", 
                "url": n.get('url')
            })
        if len(news_items) > 0:
            funds['news_score'] = score / len(news_items)
    except: pass
    return funds

df = fetch_market_data(symbol, timeframe)
funds = fetch_fundamental_data(symbol)

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
df['BB_High'] = bb.bollinger_hband()
df['BB_Low'] = bb.bollinger_lband()
df['ATR'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
ichi = IchimokuIndicator(high=df['high'], low=df['low'])
df['Ichi_A'] = ichi.ichimoku_a()
df['Ichi_B'] = ichi.ichimoku_b()

curr = df.iloc[-1]
price = curr['close']

# --- CONFLUENCE SCORING SYSTEM (70% Tech, 30% Funda) ---
tech_score = 35 # Neutral base
if price > curr['EMA_200']: tech_score += 7
else: tech_score -= 7
if curr['MACD'] > curr['MACD_Signal']: tech_score += 7
else: tech_score -= 7
if curr['RSI'] < 35: tech_score += 7 
elif curr['RSI'] > 65: tech_score -= 7
if price > curr['BB_Mid']: tech_score += 7
else: tech_score -= 7
if price > curr['Ichi_A'] and price > curr['Ichi_B']: tech_score += 7
elif price < curr['Ichi_A'] and price < curr['Ichi_B']: tech_score -= 7

funda_score = 15 # Neutral base
if funds['fng_value'] > 60: funda_score += 7
elif funds['fng_value'] < 40: funda_score -= 7
if funds['news_score'] > 0.1: funda_score += 8
elif funds['news_score'] < -0.1: funda_score -= 8

total_score = tech_score + funda_score

# Final Signal
signal = "NEUTRAL (Market is Ranging or Conflicting)"
signal_color = "yellow"
logic_msg = "Technicals aur Fundamentals apas mein takra rahe hain. Capital bachayen aur wait karein."

if total_score >= 70 and curr['ADX'] > 20:
    signal = "STRONG BUY 🚀"
    signal_color = "#00FF00"
    logic_msg = "PERFECT SETUP: Chart bhi oopar ki taraf hai aur News bhi positive hain!"
elif total_score <= 30 and curr['ADX'] > 20:
    signal = "STRONG SELL 🩸"
    signal_color = "#FF0000"
    logic_msg = "PERFECT SETUP: Chart bhi neechay gira raha hai aur News bhi negative (bearish) hain!"

st.markdown("---")

# --- 1. OVERALL NATEEJA (THE SIGNAL) ---
st.markdown("## 🎯 Overall Nateeja (Final Verdict)")
st.markdown(f"""
<div style="background-color: #111; padding: 25px; border-radius: 12px; border-top: 6px solid {signal_color}; text-align: center;">
    <h1 style="color: {signal_color}; margin: 0;">{signal}</h1>
    <h4 style="color: #ccc; margin: 10px 0;">{logic_msg}</h4>
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

# --- TABS FOR EXPLAINERS ---
tab1, tab2, tab3 = st.tabs(["🌍 Fundamental Analysis (News)", "🧠 Technical Explainer", "📊 Professional Chart"])

with tab1:
    st.markdown("## 🌍 Fundamental Market Explainer")
    st.markdown("Yeh section Artificial Intelligence (NLP) ka istemal kar ke live news aur market ki nafsiyat samajhta hai.")
    
    colF1, colF2 = st.columns(2)
    with colF1:
        st.markdown('<div class="fund-box">', unsafe_allow_html=True)
        st.markdown(f"**🧠 Fear & Greed Index (Value: {funds['fng_value']}/100)**", unsafe_allow_html=True)
        st.progress(funds['fng_value'] / 100.0)
        if funds['fng_value'] > 60:
            st.warning("**Nateeja:** Market is waqt 'Greed' (Lalach) mein hai. Aksar log buy kar rahe hain jo ke aik khatarnaak/risky sign ho sakta hai.")
        elif funds['fng_value'] < 40:
            st.success("**Nateeja:** Market is waqt 'Fear' (Dar) mein hai. Aksar log darr ke baich rahe hain, yeh kharidne (Buy) ka acha waqt ho sakta hai.")
        else:
            st.info("**Nateeja:** Market bilkul normal hai, na khauf hai na lalach.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with colF2:
        st.markdown('<div class="fund-box">', unsafe_allow_html=True)
        sentiment_word = "🟢 Bullish (Positive)" if funds['news_score'] > 0.05 else "🔴 Bearish (Negative)" if funds['news_score'] < -0.05 else "⚪ Neutral"
        st.markdown(f"**📰 AI News Sentiment Score:** {funds['news_score']:.2f}", unsafe_allow_html=True)
        if funds['news_score'] > 0.05:
            st.success(f"**Nateeja:** {sentiment_word} - Global news is coin ke haq mein hain.")
        elif funds['news_score'] < -0.05:
            st.error(f"**Nateeja:** {sentiment_word} - Global news is coin ke khilaf (negative) hain.")
        else:
            st.info(f"**Nateeja:** {sentiment_word} - Koi khaas badi news nahi aayi.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### 📡 Top 10 Breaking News (AI Evaluated)")
    for n in funds['news_list']:
        st.write(f"- {n['sentiment']} | [{n['title']}]({n['url']})")

with tab2:
    st.markdown("## 🧠 Deep Technical Explainer")
    st.markdown("Market ko practically samjhein ke pichle background mein Technical chart ka math kya keh raha hai.")

    colA, colB = st.columns(2)
    with colA:
        st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
        st.markdown(f"**📈 1. Macro Trend (EMA 200)**", unsafe_allow_html=True)
        if price > curr['EMA_200']: st.success("**Nateeja:** Price bari Moving Average ke oopar hai. Bara trend Bullish (Uptrend) hai.")
        else: st.error("**Nateeja:** Price bari Moving Average ke neechay hai. Bara trend Bearish (Downtrend) hai.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
        st.markdown(f"**⚡ 2. Momentum (MACD Crossover)**", unsafe_allow_html=True)
        if curr['MACD'] > curr['MACD_Signal']: st.success("**Nateeja:** MACD ne neechay se oopar cross kiya hai. Buying pressure barh raha hai.")
        else: st.error("**Nateeja:** MACD signal line ke neechay hai. Selling pressure zyada hai.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
        st.markdown(f"**☁️ 3. Ichimoku Cloud**", unsafe_allow_html=True)
        if price > curr['Ichi_A'] and price > curr['Ichi_B']: st.success("**Nateeja:** Price Cloud ke oopar hai. Cloud ab mazboot Support hai.")
        elif price < curr['Ichi_A'] and price < curr['Ichi_B']: st.error("**Nateeja:** Price Cloud ke neechay hai. Market mein bhaari resistance hai.")
        else: st.warning("**Nateeja:** Price Cloud ke andar phasi hui hai (No-Trade Zone).")
        st.markdown('</div>', unsafe_allow_html=True)

    with colB:
        st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
        st.markdown(f"**⚖️ 4. RSI Condition (Value: {curr['RSI']:.1f})**", unsafe_allow_html=True)
        if curr['RSI'] < 35: st.success("**Nateeja:** Market Oversold hai (Gir chuki hai). Bounce/Pump aane ka chance hai.")
        elif curr['RSI'] > 65: st.error("**Nateeja:** Market Overbought hai (Mehngi hai). Dump/Giraawat aa sakti hai.")
        else: st.info("**Nateeja:** RSI Normal range mein hai. Market stable hai.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
        st.markdown(f"**🔥 5. ADX Trend Strength (Value: {curr['ADX']:.1f})**", unsafe_allow_html=True)
        if curr['ADX'] > 25: st.success("**Nateeja:** Trend mein bohat Taqat (Volume) hai. Movement mazboot hai.")
        else: st.warning("**Nateeja:** ADX 25 se kam hai. Trend kamzor hai aur market sideways time waste kar rahi hai.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="explainer-box">', unsafe_allow_html=True)
        st.markdown(f"**📏 6. ATR Volatility (Stop-Loss logic)**", unsafe_allow_html=True)
        st.info(f"**Nateeja:** Ek average candle lag bhag ${curr['ATR']:,.2f} ki ban rahi hai. SL aur TP is hisab se hain taake market shor se trade hit na ho.")
        st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown("## 📊 Professional Master Chart")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='#FFA500', width=1.5), name='EMA 50'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='#FF0055', width=2), name='EMA 200'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['Ichi_A'], line=dict(color='rgba(0,255,0,0)'), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['Ichi_B'], line=dict(color='rgba(0,255,0,0)'), fill='tonexty', fillcolor='rgba(0,255,0,0.1)', name='Ichimoku Cloud'), row=1, col=1)
    
    colors = ['#00FF00' if val >= 0 else '#FF0000' for val in df['MACD_Hist']]
    fig.add_trace(go.Bar(x=df['timestamp'], y=df['MACD_Hist'], marker_color=colors, name='MACD Hist'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MACD'], line=dict(color='#00F0FF', width=1.5), name='MACD'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MACD_Signal'], line=dict(color='#FFA500', width=1), name='Signal'), row=2, col=1)

    fig.update_layout(template="plotly_dark", height=700, margin=dict(l=0, r=0, t=20, b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
