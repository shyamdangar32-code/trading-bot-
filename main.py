def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten columns and ensure a numeric Close exists, handling odd yfinance shapes."""
    # Flatten any MultiIndex to simple names
    if isinstance(df.columns, pd.MultiIndex):
        # Try select first ticker slice; else flatten levels
        try:
            first_ticker = sorted({c[0] for c in df.columns})[0]
            df = df[first_ticker]
        except Exception:
            df.columns = [c[1] if isinstance(c, tuple) and len(c) > 1 else str(c) for c in df.columns]
    else:
        df.columns = [str(c) for c in df.columns]

    # Bring the index out as a date column if needed
    df = df.reset_index()

    # Standard rename if present
    if "Date" in df.columns: df = df.rename(columns={"Date": "date"})

    # --- Ensure Close exists ---
    # 1) Normal case
    if "Close" not in df.columns and "Adj Close" in df.columns:
        df["Close"] = df["Adj Close"]

    # 2) Ticker-only series case (e.g., ['date','^NSEI'])
    if "Close" not in df.columns:
        non_date_cols = [c for c in df.columns if c.lower() not in ("date",)]
        # If there is exactly one non-date column, assume it's the close
        if len(non_date_cols) == 1:
            only_col = non_date_cols[0]
            df["Close"] = df[only_col]

    # 3) Last resort: raise if still missing
    if "Close" not in df.columns:
        raise RuntimeError(f"'Close' column missing. Columns found: {list(df.columns)}")

    # Ensure numeric
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"]).copy()

    # Try to parse date
    if "date" in df.columns:
        try: df["date"] = pd.to_datetime(df["date"])
        except Exception: pass

    return df
