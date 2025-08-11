import os, requests
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator


TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send(msg):
    print("SEND ->", msg)
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ No Telegram credentials set")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=20,
        )
        r.raise_for_status()
    except Exception as e:
        print("Telegram send failed:", repr(e))


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten any MultiIndex and ensure we have 'Close'."""
    # Flatten MultiIndex -> single strings
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["|".join([str(c) for c in col if c]) for col in df.columns]
    else:
        df.columns = [str(c) for c in df.columns]

    # Find a 'Close' column
    close_candidates = [c for c in df.columns if "Close" in c]
    if not close_candidates and len(df.columns) == 1:
        df = df.rename(columns={df.columns[0]: "Close"})
    elif close_candidates:
        df = df.rename(columns={close_candidates[0]: "Close"})
    else:
        raise RuntimeError(f"'Close' column missing. Found: {df.columns.tolist()}")

    df = df.reset_index()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"])
    return df


def fetch_nifty_daily():
    df = yf.download("^NSEI", period="6mo", interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError("No data from yfinance")
    return _normalize_columns(df)


def analyze(df):
    rsi = RSIIndicator(close=df["Close"], window=14).rsi()
    last = df.iloc[-1]
    last_rsi = rsi.iloc[-1]
    sig = "BUY" if last_rsi < 30 else "SELL" if last_rsi > 70 else "HOLD"
    return f"📈 NIFTY {last['Date']}\nClose: {last['Close']:.2f}\nRSI(14): {last_rsi:.2f}\nSignal: {sig}"


def run_once():
    try:
        df = fetch_nifty_daily()
        msg = analyze(df)
        print(msg)
        send(msg)
    except Exception as e:
        err = f"❗ Bot error: {e}"
        print(err)
        send(err)
        raise


if __name__ == "__main__":
    run_once()
