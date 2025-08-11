import os
import sys
import json
import time
import traceback
from typing import Optional

import pandas as pd
import numpy as np
import requests
import yfinance as yf
from ta.momentum import RSIIndicator

# --- Env (all optional except Telegram if you want alerts)
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "").strip()

Z_API_KEY    = os.getenv("ZERODHA_API_KEY", "").strip()
Z_API_SECRET = os.getenv("ZERODHA_API_SECRET", "").strip()
Z_ACCESS     = os.getenv("ZERODHA_ACCESS_TOKEN", "").strip()  # optional (daily session token)

# --- Safe Telegram sender -----------------------------------------------------
def tgsend(text: str) -> None:
    """Send a Telegram message if creds exist; always log to console."""
    print(text)
    if not TG_TOKEN or not TG_CHAT:
        print("⚠️  No Telegram creds present; skipping Telegram send.")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text},
            timeout=20,
        )
        print("Telegram response:", r.status_code, r.text[:300])
    except Exception as e:
        print("Telegram error:", e)

# --- Zerodha (optional) -------------------------------------------------------
def get_kite():
    """
    Return an authenticated KiteConnect client if api_key + access_token exist.
    We do NOT place any orders here. This is only to verify connectivity or
    fetch data once you’re ready. (Paper mode until you explicitly approve live.)
    """
    if not Z_API_KEY or not Z_ACCESS:
        return None
    try:
        from kiteconnect import KiteConnect
    except Exception:
        print("ℹ️  kiteconnect not installed; skipping Zerodha step.")
        return None
    try:
        kite = KiteConnect(api_key=Z_API_KEY)
        kite.set_access_token(Z_ACCESS)
        # quick harmless call — user profile
        _ = kite.margins()  # proves token works without placing orders
        print("✅ Zerodha: access token seems valid.")
        return kite
    except Exception as e:
        print("⚠️  Zerodha init failed:", e)
        return None

# --- Data & Signals -----------------------------------------------------------
def fetch_nifty_daily(period="6mo", interval="1d") -> pd.DataFrame:
    df = yf.download("^NSEI", period=period, interval=interval, auto_adjust=True, progress=False)
    if df is None or len(df) == 0:
        raise RuntimeError("No data from Yahoo for ^NSEI.")
    # yfinance sometimes returns MultiIndex columns for adjusted data; normalize
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df.columns = [lvl[1] if lvl[1] else lvl[0] for lvl in df.columns]
        except Exception:
            df.columns = [str(c[-1] if isinstance(c, tuple) else c) for c in df.columns]
    if "Close" not in df.columns:
        raise RuntimeError(f"'Close' column missing. Columns found: {list(df.columns)}")
    df = df.rename_axis("Date").reset_index()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"]).reset_index(drop=True)
    return df

def compute_signal(df: pd.DataFrame) -> Optional[dict]:
    """
    Strategy: EMA20 crossover filtered by RSI(14).
    BUY  when price crosses above EMA20 and RSI in 30–50.
    SELL when price crosses below EMA20 and RSI > 70.
    Returns last signal dict or None.
    """
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["RSI"]   = RSIIndicator(close=df["Close"], window=14).rsi()

    sig_idx = None
    for i in range(1, len(df)):
        rsi = df.at[i, "RSI"]
        c, p  = df.at[i, "Close"], df.at[i-1, "Close"]
        e, ep = df.at[i, "EMA20"], df.at[i-1, "EMA20"]
        if pd.notna(rsi) and pd.notna(c) and pd.notna(p) and pd.notna(e) and pd.notna(ep):
            up   = (p < ep) and (c > e)
            down = (p > ep) and (c < e)
            if 30 <= rsi <= 50 and up:
                df.at[i, "Signal"] = "BUY"
                sig_idx = i
            elif rsi > 70 and down:
                df.at[i, "Signal"] = "SELL"
                sig_idx = i

    if sig_idx is None:
        return None
    row = df.iloc[sig_idx]
    return {
        "date":  str(pd.to_datetime(row["Date"]).date()),
        "signal": row["Signal"],
        "close":  float(row["Close"]),
        "ema20":  float(row["EMA20"]),
        "rsi":    float(row["RSI"]),
    }

def main():
    try:
        # Optional Zerodha connect (no trading; just check token if supplied)
        kite = get_kite()

        # Data + signal
        df = fetch_nifty_daily()
        out = compute_signal(df)

        if not out:
            tgsend("📝 No new NIFTY signal this run.")
            return

        msg = (
            f"🚨 NIFTY Signal: {out['signal']}\n"
            f"Date: {out['date']}\n"
            f"Close: {out['close']:.2f}\n"
            f"EMA20: {out['ema20']:.2f}\n"
            f"RSI(14): {out['rsi']:.2f}"
        )
        tgsend(msg)

        # If you later want *paper* logs tied to Zerodha quotes, you can add:
        if kite:
            # harmless LTP fetch (no order)
            try:
                ltp = kite.ltp(["NSE:NIFTY 50"]).get("NSE:NIFTY 50", {}).get("last_price")
                if ltp:
                    tgsend(f"ℹ️ Zerodha LTP check: NIFTY ~ {ltp}")
            except Exception as e:
                print("Zerodha LTP fetch failed:", e)

    except Exception as e:
        err = f"❌ Bot error: {e}\n{traceback.format_exc()[-800:]}"
        tgsend(err)
        # re-raise so Actions marks the job as failed (useful for debugging)
        raise

if __name__ == "__main__":
    main()
