import asyncio
import json
import websockets
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
import requests
from datetime import datetime

# Configuration
SYMBOL = "btcusdt"  # Bitcoin to USD Tether
INTERVAL = "1m"     # 1 minute candles
WS_URL = f"wss://stream.binance.com:9443/ws/{SYMBOL}@kline_{INTERVAL}"
REST_URL = "https://api.binance.com/api/v3/klines"

# Historical data storage
candles_data = []
MAX_CANDLES = 100 # Keep last 100 candles in memory for TA

def fetch_historical_data():
    """Fetch initial historical data so TA indicators have enough data to calculate immediately."""
    print(f"[*] Fetching historical data for {SYMBOL.upper()}...")
    params = {
        'symbol': SYMBOL.upper(),
        'interval': INTERVAL,
        'limit': MAX_CANDLES
    }
    response = requests.get(REST_URL, params=params)
    data = response.json()
    
    for kline in data:
        candle = {
            'timestamp': pd.to_datetime(kline[0], unit='ms'),
            'open': float(kline[1]),
            'high': float(kline[2]),
            'low': float(kline[3]),
            'close': float(kline[4]),
            'volume': float(kline[5])
        }
        candles_data.append(candle)
    print(f"[*] Loaded {len(candles_data)} historical candles successfully.")

async def analyze_market(data):
    """
    Apply Technical Analysis on the collected candles.
    """
    if len(data) < 20:
        return

    # Convert list of dicts to Pandas DataFrame
    df = pd.DataFrame(data)
    
    # Calculate Indicators using the 'ta' library (compatible with all Python versions)
    df['RSI_14'] = RSIIndicator(close=df['close'], window=14).rsi()
    df['EMA_9'] = EMAIndicator(close=df['close'], window=9).ema_indicator()
    df['EMA_21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()

    latest = df.iloc[-1]
    
    rsi_val = latest.get('RSI_14', float('nan'))
    ema9 = latest.get('EMA_9', float('nan'))
    ema21 = latest.get('EMA_21', float('nan'))
    close_price = latest['close']

    print(f"\n=== Technical Analysis Update ({datetime.now().strftime('%H:%M:%S')}) ===")
    print(f"Price: ${close_price:.2f}")
    
    if not pd.isna(rsi_val):
        status = "[OVERSOLD - GOOD FOR BUY]" if rsi_val < 30 else "[OVERBOUGHT - RISK OF DROP]" if rsi_val > 70 else "[NEUTRAL]"
        print(f"RSI (14): {rsi_val:.2f} {status}")
        
    if not pd.isna(ema9) and not pd.isna(ema21):
        trend = "BULLISH (UP)" if ema9 > ema21 else "BEARISH (DOWN)"
        print(f"Trend (EMA 9 vs 21): {trend}")
    
    # Basic Signal Logic (Confluence)
    if rsi_val < 30 and ema9 > ema21:
        print("🚀 SIGNAL GENERATED: POTENTIAL BUY (Oversold + Bullish Trend)")
    elif rsi_val > 70 and ema9 < ema21:
        print("🚨 SIGNAL GENERATED: POTENTIAL SELL (Overbought + Bearish Trend)")
    print("========================================================\n")

async def binance_ws():
    """
    Connect to Binance WebSocket and fetch real-time candlestick data.
    """
    print(f"[*] Connecting to Binance Live WebSocket for {SYMBOL.upper()}...")
    
    async with websockets.connect(WS_URL) as ws:
        print("[*] Connected! Waiting for live market data stream...\n")
        
        # Run initial analysis on the historical data we just fetched
        await analyze_market(candles_data)
        
        while True:
            try:
                message = await ws.recv()
                payload = json.loads(message)
                
                kline = payload['k']
                is_closed = kline['x']
                current_price = float(kline['c'])
                
                # Real-time price update (tick by tick)
                print(f"Live Tick Price: ${current_price:.2f} (Waiting for 1m candle close...)", end="\r")
                
                # When a 1-minute candle fully closes, save it and run deep analysis
                if is_closed:
                    candle = {
                        'timestamp': pd.to_datetime(kline['t'], unit='ms'),
                        'open': float(kline['o']),
                        'high': float(kline['h']),
                        'low': float(kline['l']),
                        'close': float(kline['c']),
                        'volume': float(kline['v'])
                    }
                    candles_data.append(candle)
                    
                    # Prevent memory overflow by keeping only last MAX_CANDLES
                    if len(candles_data) > MAX_CANDLES:
                        candles_data.pop(0)
                        
                    # Trigger the analysis engine
                    await analyze_market(candles_data)
                    
            except Exception as e:
                print(f"\n[!] Error in WebSocket: {e}")
                await asyncio.sleep(5)
                break

if __name__ == "__main__":
    print("=======================================")
    print("   QUANT TRADING ENGINE - INITIALIZED")
    print("=======================================\n")
    fetch_historical_data()
    try:
        asyncio.run(binance_ws())
    except KeyboardInterrupt:
        print("\n[*] Engine Stopped by User.")
