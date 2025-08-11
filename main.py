import os
import requests
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator

# --- Config from GitHub Secrets / env ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SEND_ONLY = os.getenv("SEND_ONLY_SIGNALS", "false").lower() == "true"


def send(msg: str) -> None:
    """Send a message to Telegram (no-op if token/chat not set)."""
    print("SEND ->", msg)
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ No Telegram credentials set")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("Telegram send failed:", repr(e))


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns and make sure we have a numeric Close column and a Date column."""
    # Flatten possible MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            "|".join([str(c) for c in tup if str(c) != "None"])
            for tup in df.columns.to_list()
        ]
    else:
        df.columns = [str(c) for c in df.columns]

    # Pick a column that looks like 'Close'
    lower = [c.lower() for c in df.columns]
    close_candidates = [c for c, lc in zip(df.columns, lower) if "close" in lc]
    if not close_candidates:
        raise RuntimeError(f"'Close' column missing. Columns found: {list(df.columns)}")
    close_col = close_candidates[0]

    # Ensure we have a Date column
    if "Date" not in df.columns:
        df = df.reset_index()
        if "Date" not in df.columns and "date" in df.columns:
            df.rename(columns={"date": "Date"}, inplace=True)

    # Ensure numeric Close
    df["Close"] = pd.to_numeric(df[close_col], errors="coerce")
    df = df.dropna(subset=["Close"]).copy()
    return df


def fetch_nifty_daily() -> pd.DataFrame:
    """Fetch last ~6 months of NIFTY (^NSEI) daily candles via yfinance."""
    df = yf.download("^NSEI", period="6mo", interval="1d", progress=False)
    if df is None or df.empty:
        raise RuntimeError("No data from yfinance.")
    return _normalize_columns(df)


def analyze(df: pd.DataFrame) -> dict:
    """Compute RSI(14) and produce signal + pretty message."""
    rsi_series = RSIIndicator(close=df["Close"], window=14).rsi()
    last = df.iloc[-1]
    last_rsi = float(rsi_series.iloc[-1])

    sig = "HOLD"
    if last_rsi < 30:
        sig = "BUY"
    elif last_rsi > 70:
        sig = "SELL"

    msg = (
        f"📉 NIFTY {str(last.get('Date', ''))[:10]}\n"
        f"Close: {last['Close']:.2f}\n"
        f"RSI(14): {last_rsi:.1f}\n"
        f"Signal: {sig}"
    )
    return {"msg": msg, "signal": sig}


def run_once() -> None:
    try:
        df = fetch_nifty_daily()
        out = analyze(df)
        print(out["msg"])

        # Only alert on BUY/SELL if toggled on
        if (not SEND_ONLY) or (out["signal"] in {"BUY", "SELL"}):
            send(out["msg"])
        else:
            print("Skipping Telegram (HOLD and SEND_ONLY_SIGNALS=true).")
    except Exception as e:
        err = f"❗ Bot error: {e}"
        print(err)
        # still notify on errors
        send(err)
        raise


if __name__ == "__main__":
    run_once()
