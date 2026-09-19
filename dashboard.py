import streamlit as st
import pandas as pd
import requests
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import AverageTrueRange, BollingerBands
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- UI SETUP (Mobile Friendly & Clean) ---
st.set_page_config(page_title="Pro AI Trading", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .big-title {font-size: 32px; font-weight: bold; color: #ffffff;}
    .sub-text {font-size: 14px; color: #aaaaaa; margin-bottom: 20px;}
    .signal-box {padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center;}
    .target-text {font-size: 18px; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">🤖 AI Trading Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Aapke liye simple, clear aur highly accurate market signals.</div>', unsafe_allow_html=True)

# --- SIMPLE SELECTORS (Top of page, great for mobile) ---
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
default_index = all_symbols.index("BTCUSDT") if "BTCUSDT" in all_symbols else 0

col1, col2 = st.columns(2)
symbol = col1.selectbox("🪙 Coin Select Karein", all_symbols, index=default_index)
timeframe = col2.selectbox("⏱️ Timeframe", ["1m", "5m", "15m", "30m", "1h", "4h", "1d"], index=2)

# --- DATA FETCHING ---
@st.cache_data(ttl=60)
def fetch_market_data(sym, tf):
    kucoin_tf = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
    try:
        res = requests.get("https://api.kucoin.com/api/v1/market/candles", params={"symbol": sym.replace("USDT", "-USDT"), "type": kucoin_tf.get(tf, "15min")}, timeout=5)
        if res.status_code == 200 and res.json().get('data'):
            df = pd.DataFrame(res.json()['data'], columns=['timestamp', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='s')
            for col in ['open', 'high', 'low', 'close']: df[col] = df[col].astype(float)
            return df.sort_values('timestamp').reset_index(drop=True)
    except: pass
    
    for url in ["https://api.binance.us/api/v3/klines", "https://api.binance.com/api/v3/klines"]:
        try:
            res = requests.get(url, params={"symbol": sym, "interval": tf, "limit": 250}, timeout=5)
            if res.status_code == 200:
                df = pd.DataFrame(res.json(), columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'c', 'q', 'n', 'tb', 'tq', 'i'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close']: df[col] = df[col].astype(float)
                return df
        except: continue
    return None

df = fetch_market_data(symbol, timeframe)
if df is None or len(df) < 50:
    st.error("🚨 Connection Error: Data nahi mil raha.")
    st.stop()

# --- BACKGROUND CALCULATIONS (Hidden from UI) ---
df['EMA_21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()
df['EMA_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
df['EMA_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
macd = MACD(close=df['close'])
df['MACD'] = macd.macd()
df['MACD_Signal'] = macd.macd_signal()
df['MACD_Hist'] = macd.macd_diff()
df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
df['Stoch'] = StochasticOscillator(high=df['high'], low=df['low'], close=df['close']).stoch()
bb = BollingerBands(close=df['close'], window=20, window_dev=2)
df['BB_High'] = bb.bollinger_hband()
df['BB_Mid'] = bb.bollinger_mavg()
df['BB_Low'] = bb.bollinger_lband()
df['ADX'] = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14).adx()
df['ATR'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()

curr = df.iloc[-1]
current_price = curr['close']

# --- SCORING ---
score = 50
if current_price > curr['EMA_200']: score += 10
else: score -= 10
if curr['EMA_21'] > curr['EMA_50']: score += 10
else: score -= 10
if curr['MACD'] > curr['MACD_Signal']: score += 10
else: score -= 10
if 40 < curr['RSI'] < 70: score += 5
elif curr['RSI'] < 30: score += 10
elif curr['RSI'] > 70: score -= 10
if current_price > curr['BB_Mid']: score += 5 
else: score -= 5
score = max(0, min(100, score))

# --- CLEAR SIGNAL LOGIC ---
signal = "WAIT"
sl, tp = 0, 0
logic_msg = "Market abhi clear nahi hai. Koi trade na lein, apne capital ko safe rakhein."

if score >= 75 and curr['ADX'] > 20:
    signal = "BUY"
    sl = current_price - (curr['ATR'] * 1.5)
    tp = current_price + (curr['ATR'] * 3.0)
    logic_msg = "Market ka overall trend oopar ki taraf hai aur kharidari (buying) ki taqat zyada hai."
elif score <= 25 and curr['ADX'] > 20:
    signal = "SELL"
    sl = current_price + (curr['ATR'] * 1.5)
    tp = current_price - (curr['ATR'] * 3.0)
    logic_msg = "Market tezi se gir rahi hai aur baichne walon (sellers) ka control hai."

st.markdown("---")

# --- MOST IMPORTANT: THE CLEAR SIGNAL UI ---
st.markdown("### 🎯 AI SIGNAL (Aapko kya karna chahiye?)")

if signal == "BUY":
    st.success(f"### 🟢 ACTION: STRONG BUY (LONG)\n{logic_msg}")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 Entry Price", f"${current_price:,.4f}")
    c2.metric("💰 Take Profit (Target)", f"${tp:,.4f}")
    c3.metric("🛡️ Stop Loss", f"${sl:,.4f}")
elif signal == "SELL":
    st.error(f"### 🔴 ACTION: STRONG SELL (SHORT)\n{logic_msg}")
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 Entry Price", f"${current_price:,.4f}")
    c2.metric("💰 Take Profit (Target)", f"${tp:,.4f}")
    c3.metric("🛡️ Stop Loss", f"${sl:,.4f}")
else:
    st.warning(f"### 🟡 ACTION: WAIT (Sabar Karein)\n{logic_msg}")

st.markdown("---")

# --- CLEAN TABS FOR CHARTS AND DETAILS ---
tab1, tab2, tab3 = st.tabs(["📊 Main Chart", "🧠 AI Logic Details", "📉 Advance Oscillators"])

with tab1:
    st.markdown("**Price aur Trend Lines (Bollinger & EMAs)**")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['BB_High'], line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dot'), name='BB High'))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['BB_Low'], line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(255,255,255,0.05)', name='BB Low'))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='#FFA500', width=1.5), name='EMA 50 (Short Trend)'))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='#FF0055', width=2), name='EMA 200 (Macro Trend)'))
    
    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0, r=0, t=10, b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.markdown("#### AI ne yeh signal kyun diya? (Asan alfaz mein)")
    st.write(f"- **Macro Trend (Bara Trend):** Price 200-EMA ke {'oopar' if current_price > curr['EMA_200'] else 'neechay'} hai, isliye bara trend {'Uptrend (Bullish)' if current_price > curr['EMA_200'] else 'Downtrend (Bearish)'} hai.")
    st.write(f"- **Short Trend (Chota Trend):** {'Kharidari' if curr['EMA_21'] > curr['EMA_50'] else 'Farokht'} ki taqat zyada hai.")
    st.write(f"- **RSI (Overbought/Oversold):** Score {curr['RSI']:.1f} hai. (Agar 30 se kam ho toh oversold, 70 se zyada ho toh overbought).")
    st.write(f"- **ADX (Trend ki taqat):** {curr['ADX']:.1f} (Agar 20 se kam ho toh market phasi hui hai, trade na lein).")
    st.write(f"- **Overall AI Score:** **{score}% Bullish**")

with tab3:
    st.markdown("**MACD & RSI (Momentum Checking)**")
    fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.5], vertical_spacing=0.1)
    
    # MACD
    colors = ['#00FF00' if val >= 0 else '#FF0000' for val in df['MACD_Hist']]
    fig2.add_trace(go.Bar(x=df['timestamp'], y=df['MACD_Hist'], marker_color=colors, name='MACD'), row=1, col=1)
    fig2.add_trace(go.Scatter(x=df['timestamp'], y=df['MACD'], line=dict(color='#00F0FF', width=1.5), name='MACD Line'), row=1, col=1)
    # RSI
    fig2.add_trace(go.Scatter(x=df['timestamp'], y=df['RSI'], line=dict(color='#E0B0FF', width=1.5), name='RSI'), row=2, col=1)
    fig2.add_hline(y=70, line=dict(color='red', width=1, dash='dash'), row=2, col=1)
    fig2.add_hline(y=30, line=dict(color='green', width=1, dash='dash'), row=2, col=1)
    
    fig2.update_layout(template="plotly_dark", height=450, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig2, use_container_width=True)
