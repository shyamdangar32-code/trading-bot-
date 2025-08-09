
import os, requests, numpy as np, pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("WARN: Missing TELEGRAM envs; skipping Telegram send.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=20)
        r.raise_for_status()
        print("Telegram OK", r.status_code)
    except Exception as e:
        print("Telegram send failed:", e)

def fetch(symbol="^NSEI", period="6mo", interval="1d") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise ValueError("No data.")
    df = df.rename_axis("Date").reset_index()
    # ensure numeric
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"]).copy()
    return df

def analyze(df: pd.DataFrame) -> dict:
    rsi = RSIIndicator(close=df["Close"], window=14).rsi()
    last = df.iloc[-1]
    last_rsi = float(rsi.iloc[-1])
    sig = "HOLD"
    if last_rsi < 30: sig = "BUY"
    elif last_rsi > 70: sig = "SELL"
    return {"date": str(last["Date"])[:10], "close": float(last["Close"]), "rsi": last_rsi, "signal": sig}

def run_once():
    try:
        df = fetch("^NSEI", "6mo", "1d")
        out = analyze(df)
        text = f"📈 NIFTY summary {out['date']}
Close: {out['close']:.2f}
RSI(14): {out['rsi']:.1f}
Signal: {out['signal']}"
        print(text)
        send(text)
    except Exception as e:
        send(f"❗Bot error: {e}")
        raise

if __name__ == "__main__":
    run_once()
