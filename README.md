# trading-bot

Minimal NIFTY bot:
- Downloads data with `yfinance`
- Computes RSI(14)
- Sends signal to Telegram

## Setup (GitHub Actions)
Repo → Settings → Secrets → Actions
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Actions → *Run Trading Bot* → **Run workflow**

## Setup (Render Cron) [optional]
- New Blueprint → use this repo (render.yaml)
- Set env vars in Render dashboard
