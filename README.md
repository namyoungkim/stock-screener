# Stock Screener

Value investing screening tool for US and Korean stocks.

## Features

- **Screening**: Filter stocks by valuation, profitability, and financial health metrics
- **Watchlist**: Save and track your favorite stocks
- **Alerts**: Get notified when stocks meet your criteria
- **Multi-language**: English and Korean support
- **Discord Bot**: Screen stocks directly from Discord

## Tech Stack

- **Frontend**: Next.js 14, Tailwind CSS, next-intl
- **Backend**: FastAPI
- **Database**: Supabase (PostgreSQL)
- **Bot**: discord.py
- **Data**: yfinance, FMP, OpenDartReader
- **Deploy**: Vercel, Railway

## Project Structure

```
stock-screener/
├── backend/           # FastAPI server
├── frontend/          # Next.js app
├── data-pipeline/     # Data collection scripts
├── discord-bot/       # Discord bot
└── .github/workflows/ # GitHub Actions
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Supabase account
- FMP API key (free tier)
- Discord bot token

### Setup

1. Clone the repository
```bash
git clone https://github.com/namyoungkim/stock-screener.git
cd stock-screener
```

2. Install dependencies
```bash
uv sync
```

3. Copy environment variables
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Environment Variables

```
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# FMP (Financial Modeling Prep)
FMP_API_KEY=your_fmp_key

# DART (Korea)
DART_API_KEY=your_dart_key

# Discord
DISCORD_BOT_TOKEN=your_discord_token
```

## License

MIT
