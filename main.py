# --- Standard imports (must be first)
from __future__ import annotations
import os, sys, json, time
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator


# ========== Config from environment ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TG_CHAT_ID")

# Optional (not used yet, just read so we can verify secrets exist)
ZERODHA_API_KEY    = os.getenv("ZERODHA_API_KEY")
ZERODHA_API_SECRET = os.getenv("ZERODHA_API_SECRET")


# ========== Helpers ==========
def send(msg: str) -> None:
    """Send a message to Telegram if credentials exist; otherwise print."""
    print("SEND ->", msg.replace("\n", " | ")[:400])
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print("⚠️  No Telegram credentials set; printing only.")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg},
            timeout=20,
        )
        r.raise_for_status()
        print("Telegram OK:", r.status_code)
    except Exception as e:
        print("Telegram send failed:", repr(e))


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure a flat DataFrame with a single 'Close' column.
    yfinance can return MultiIndex columns (e.g., ('Close','^NSEI')).
    """
    if df is None or df.empty:
        raise RuntimeError("No data frame to normalize.")

    # If MultiIndex, try to pick the 'Close' level
    if isinstance(df.columns, pd.MultiIndex):
        # Prefer ('Close', <ticker>) if present
        if ("Close",) in set((c[0],) for c in df.columns):
            # Find first column whose first level equals 'Close'
            close_cols = [c for c in df.columns if c[0] == "Close"]
            df = df[list(close_cols[0])].to_frame() if isinstance(close_cols[0], tuple) else df[close_cols[0]]
        else:
            # Fallback: take the last level name 'Close' if exists anywhere
            try:
                close_cols = [c for c in df.columns if c[-1] == "Close"]
                df = df[close_cols[0]]
            except Exception:
                pass

    # After potential selection, flatten any remaining MultiIndex
    if isinstance(df, pd.DataFrame) and isinstance(df.columns, pd.MultiIndex):
        try:
            df.columns = ["|".join(map(str, c)).strip() for c in df.columns]
        except Exception:
            df.columns = [str(c[-1]) for c in df.columns]

    # Common cases: column might be literally 'Close' OR '^NSEI' etc.
    # If we don’t yet have 'Close', try to derive it.
    cols = [str(c) for c in df.columns]
    if "Close" not in cols:
        # If a single price series came back with name like '^NSEI', rename it to Close
        if len(cols) == 1:
            df = df.rename(columns={cols[0]: "Close"})
        else:
            # Try common price column aliases
            for cand in ("Adj Close", "Close|^NSEI", "^NSEI"):
                if cand in cols:
                    df = df.rename(columns={cand: "Close"})
                    break

    # Ensure 'Close' exists now
    if "Close" not in [str(c) for c in df.columns]:
        raise RuntimeError(f"'Close' column missing. Columns found: {list(df.columns)}")

    # Cleanup
    df = df.copy()
    if "Date" not in df.columns:
        df = df.reset_index().rename(columns={"index": "Date"})
    # Ensure numeric
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"])
    return df


def fetch_nifty_daily(period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Download NIFTY (^NSEI) data and normalize to have Date + Close."""
    df = yf.download("^NSEI", period=period, interval=interval, auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError("No data from yfinance for ^NSEI.")
    df = _normalize_columns(df)
    return df


def analyze(df: pd.DataFrame) -> dict:
    """Compute RSI(14) and a simple BUY/SELL/HOLD signal on latest bar."""
    if df.empty:
        raise RuntimeError("Empty DataFrame in analyze().")

    rsi = RSIIndicator(close=df["Close"], window=14).rsi()
    last = df.iloc[-1]
    last_rsi = float(rsi.iloc[-1])

    sig = "HOLD"
    if last_rsi < 30:
        sig = "BUY"
    elif last_rsi > 70:
        sig = "SELL"

    return {
        "date": str(last.get("Date", ""))[:19],
        "close": float(last["Close"]),
        "rsi": round(last_rsi, 2),
        "signal": sig,
    }


def run_once() -> None:
    try:
        df = fetch_nifty_daily()
        out = analyze(df)
        text = (
            f"📈 NIFTY summary {out['date']}\n"
            f"Close: {out['close']:.2f}\n"
            f"RSI(14): {out['rsi']:.2f}\n"
            f"Signal: {out['signal']}"
        )
        print(text)
        send(text)

        # Basic Zerodha secret presence check (no trading here)
        if ZERODHA_API_KEY and ZERODHA_API_SECRET:
            print("Zerodha keys detected (not used in this phase).")
        else:
            print("ℹ️ Zerodha keys not set or not needed yet.")

    except Exception as e:
        err = f"❗ Bot error: {e}"
        print(err)
        send(err)
        # Non-zero exit so GitHub Actions shows failure
        raise


if __name__ == "__main__":
    run_once()
