import os, requests, numpy as np, pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN") or os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TG_CHAT_ID") or os.getenv("CHAT_ID")

def send(msg: str) -> None:
    """Send a Telegram message, but never crash the job if it fails."""
    print("SEND ->", msg[:200].replace("\n", " "))
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("WARN: Telegram creds missing; skipping send.")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=20,
        )
        # Don’t raise on 401—just print so job continues
        if r.status_code != 200:
            print("Telegram response:", r.status_code, r.text[:200])
    except Exception as e:
        print("Telegram send failed:", e)

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance MultiIndex columns and ensure a numeric Close column exists."""
    if isinstance(df.columns, pd.MultiIndex):
        # If ticker level exists, try to pick the first (or specific) ticker slice
        tickers = sorted({lvl[0] for lvl in df.columns})
        if len(tickers) >= 1:
            t0 = tickers[0]
            try:
                df = df[t0]
            except Exception:
                # Fallback: flatten by taking the second level names
                df.columns = [c[1] if isinstance(c, tuple) and len(c) > 1 else str(c) for c in df.columns]
        else:
            df.columns = [c[1] if isinstance(c, tuple) and len(c) > 1 else str(c) for c in df.columns]
    else:
        df.columns = [str(c) for c in df.columns]

    # If Close missing, try Adj Close
    if "Close" not in df.columns and "Adj Close" in df.columns:
        df["Close"] = df["Adj Close"]

    # Basic cleaning
    if "Date" in df.columns:
        df = df.rename(columns={"Date": "date"})
    df = df.reset_index()
    if "Date" in df.columns:
        df = df.rename(columns={"Date": "date"})
    if "date" in df.columns:
        try:
            df["date"] = pd.to_datetime(df["date"])
        except Exception:
            pass

    if "Close" not in df.columns:
        raise RuntimeError(f"'Close' column missing. Columns found: {list(df.columns)}")

    # Ensure numeric
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"]).copy()
    return df

def fetch_nifty_daily() -> pd.DataFrame:
    df = yf.download("^NSEI", period="6mo", interval="1d", auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise RuntimeError("No data returned by yfinance for ^NSEI.")
    df = _normalize_columns(df)
    return df

def analyze(df: pd.DataFrame) -> dict:
    rsi = RSIIndicator(close=df["Close"], window=14)
    df = df.copy()
    df["RSI"] = rsi.rsi()

    last = df.iloc[-1]
    last_rsi = float(last["RSI"])
    sig = "HOLD"
    if last_rsi < 30:
        sig = "BUY"
    elif last_rsi > 70:
        sig = "SELL"

    return {
        "date": str(last.get("date", ""))[:10],
        "close": float(last["Close"]),
        "rsi": last_rsi,
        "signal": sig,
    }

def run_once():
    df = fetch_nifty_daily()
    out = analyze(df)
    text = (
        f"📈 NIFTY summary {out['date']}\n"
        f"Close: {out['close']:.2f}\n"
        f"RSI(14): {out['rsi']:.1f}\n"
        f"Signal: {out['signal']}"
    )
    print(text)
    send(text)

if __name__ == "__main__":
    try:
        run_once()
    except Exception as e:
        send(f"❗Bot error: {e}")
        raise
