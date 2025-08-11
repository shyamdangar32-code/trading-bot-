import os
import requests
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator


# --- Config from GitHub Secrets (trim spaces/newlines to avoid 404s) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def send(msg: str) -> None:
    """Send a Telegram message; prints errors but doesn't crash the job."""
    print("SEND ->", msg)
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ No Telegram credentials set (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("Telegram send failed:", repr(e))


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flatten any MultiIndex columns and map any variant like 'Close|^NSEI'
    to a single canonical 'Close' column (numeric, no NaNs).
    """
    # Flatten columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["|".join(map(str, c)).strip() for c in df.columns]
    else:
        df.columns = [str(c).strip() for c in df.columns]

    # Find a usable Close column
    close_col = None

    # 1) exact 'Close'
    for c in df.columns:
        if c.lower() == "close":
            close_col = c
            break

    # 2) prefix 'Close|...'
    if close_col is None:
        for c in df.columns:
            if c.lower().startswith("close|"):
                close_col = c
                break

    # 3) safety: split on '|' and check first part equals 'close'
    if close_col is None:
        for c in df.columns:
            parts = c.split("|")
            if parts and parts[0].lower() == "close":
                close_col = c
                break

    if close_col is None:
        raise RuntimeError(f"'Close' column missing. Columns found: {list(df.columns)}")

    df = df.copy()
    df["Close"] = pd.to_numeric(df[close_col], errors="coerce")
    df = df.reset_index()          # Ensure a Date column exists from index
    df = df.dropna(subset=["Close"])
    return df


def fetch_nifty_daily() -> pd.DataFrame:
    """Download NIFTY (^NSEI) daily candles (last ~6 months)."""
    df = yf.download(
        "^NSEI",
        period="6mo",
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if df is None or df.empty:
        raise RuntimeError("No data from yfinance for ^NSEI")
    return _normalize_columns(df)


def analyze(df: pd.DataFrame) -> str:
    """Compute RSI(14) and produce a human-readable signal message."""
    rsi = RSIIndicator(close=df["Close"], window=14, fillna=False)
    last_row = df.iloc[-1]
    last_rsi = float(rsi.rsi().iloc[-1])

    signal = "HOLD"
    if last_rsi < 30:
        signal = "BUY"
    elif last_rsi > 70:
        signal = "SELL"

    date_str = str(last_row.get("Date", ""))[:10]
    close_val = float(last_row["Close"])
    return (
        f"📈 NIFTY {date_str}\n"
        f"Close: {close_val:.2f}\n"
        f"RSI(14): {last_rsi:.1f}\n"
        f"Signal: {signal}"
    )


def run_once():
    try:
        df = fetch_nifty_daily()
        msg = analyze(df)
        print(msg)
        send(msg)
    except Exception as e:
        err = f"❗Bot error: {e}"
        print(err)
        send(err)
        raise


if __name__ == "__main__":
    run_once()
