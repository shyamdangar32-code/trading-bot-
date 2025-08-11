import os, requests
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator

# --- Telegram secrets from GitHub Actions (or your local env)
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send(msg: str) -> None:
    """Send a Telegram message if credentials exist; otherwise just print."""
    print("SEND ->", msg)
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ No Telegram credentials set; printing only.")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=20,
        )
        # Show 401/404 etc. in logs but don't crash the run
        if r.status_code != 200:
            print("Telegram response:", r.status_code, r.text[:200])
        r.raise_for_status()
    except Exception as e:
        print("Telegram send failed:", repr(e))

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns, find or create 'Close', clean & return df."""
    if df is None or df.empty:
        raise RuntimeError("No data frame to normalize.")

    # Flatten MultiIndex -> single string names
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["|".join([str(c) for c in tup if c is not None]) for tup in df.columns]
    else:
        df.columns = [str(c) for c in df.columns]

    # Prefer a column that endswith '|Close' (yfinance MultiIndex pattern)
    close_candidates = [c for c in df.columns if c.lower().endswith("|close")]
    if not close_candidates:
        # Fallback: exact 'Close'
        if "Close" in df.columns:
            close_candidates = ["Close"]

    if not close_candidates:
        # Some ^NSEI downloads can return a single series named '^NSEI'
        if "^NSEI" in df.columns:
            df = df.rename(columns={"^NSEI": "Close"})
        else:
            raise RuntimeError(f"'Close' column missing. Columns found: {list(df.columns)}")
    else:
        # Map first candidate to 'Close'
        df = df.rename(columns={close_candidates[0]: "Close"})

    # Ensure 'Date' exists as a column (not index)
    df = df.reset_index()

    # Clean numeric
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"])

    return df

def fetch_nifty_daily() -> pd.DataFrame:
    """Fetch ~6 months of daily data for NIFTY (^NSEI) and normalize."""
    df = yf.download("^NSEI", period="6mo", interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError("No data from Yahoo Finance for ^NSEI.")
    return _normalize_columns(df)

def analyze(df: pd.DataFrame) -> str:
    """Compute RSI(14) and produce a small summary message."""
    rsi = RSIIndicator(close=df["Close"], window=14)
    last = df.iloc[-1]
    last_rsi = float(rsi.rsi().iloc[-1])

    # Toy signal: BUY if RSI<30, SELL if RSI>70, else HOLD
    if last_rsi < 30:
        sig = "BUY"
    elif last_rsi > 70:
        sig = "SELL"
    else:
        sig = "HOLD"

    return (
        f"📈 NIFTY {str(last['Date'])[:10]}\n"
        f"Close: {last['Close']:.2f}\n"
        f"RSI(14): {last_rsi:.1f}\n"
        f"Signal: {sig}"
    )

def run_once():
    try:
        df = fetch_nifty_daily()
        msg = analyze(df)
        print(msg)
        send(msg)
    except Exception as e:
        err = f"❗️Bot error: {e}"
        print(err)
        send(err)
        # re-raise so the GitHub step can mark failure if something is wrong
        raise

if __name__ == "__main__":
    run_once()
