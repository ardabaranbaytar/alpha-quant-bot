# Alpha Quant — Statistical Pairs Trading Bot

A production-grade quantitative trading research platform and simulation engine built for learning and experimentation. The system autonomously screens the equity universe to detect statistical arbitrage opportunities between cointegrated stock pairs using rolling Z-score thresholds. It evaluates signals against a robust, rule-based risk management engine and executes simulated positions tracked through a real-time responsive web dashboard.

> ⚠️ **Disclaimer:** This project is developed strictly for educational and portfolio presentation purposes. It does not constitute financial or investment advice. All trading operations, margin calculations, and equity curves are entirely simulated — no real capital is deployed.

---

## Technical Architecture & Core Modules

The platform is built on a highly decoupled, modular architecture split into five key operational layers:

* **Data Pipeline (`data_pipeline/`)**: Leverages `yfinance` to fetch high-resolution, hourly OHLCV bars for the NASDAQ-100 index universe. Utilizes an asynchronous hybrid strategy running on an `APScheduler` cron: intraday delta updates fetch light 3-day snapshots, while a midnight deep sync scans a rolling 2-year horizon to preserve historical database integrity inside a PostgreSQL data warehouse.
* **Signal Engine (`core/signal_generator.py`)**: Runs systematic screening across the entire asset matrix. It evaluates stationary asset spreads using the two-step Engle-Granger cointegration test.
* **Fundamental Filter (`core/health_score.py`)**: Acts as a secondary risk overlay. Scrapes dynamic financial statements from corporate balance sheets to compute an autonomous corporate health score (0 to 100) based on profitability ratios, cash-to-debt metrics, and operating margins, filtering out fundamentally decaying assets before capital allocation.
* **Risk & Execution Engine (`execution/execution_engine.py`)**: A background worker thread running a persistent loop. It processes incoming signals against strict multi-factor portfolio constraints: real-time trailing stop-losses, daily aggregate drawdown caps, maximum overlapping stock exposures, and post-trade cooldown windows. It accounts for friction by penalizing gross returns with fixed transaction and slippage rates.
* **Web Dashboard (`web_app/`)**: A fast, asynchronous web gateway built with `FastAPI` and `Jinja2` templates. It renders active trading opportunities, the live position ledger, and calculated performance metrics powered by a lightweight, customized responsive `Three.js` WebGL watercolor shader backdrop.

---

## Quantitative Strategy Methodology

The core engine relies on the mathematical principle of Mean Reversion. For a pair of stocks A and B, the system checks if a linear combination forms a stationary time series:

Price_A - Beta * Price_B = Spread

Where Beta represents the hedge ratio and Spread is the stationary difference. If the Engle-Granger p-value falls below the significance threshold (p < 0.02), the pair enters the active radar.

The model computes a rolling Z-Score of the spread price ratio over a configurable historical lookback window (W = 300 hours):

Z = (Ratio_t - Mean_W) / Std_W

Where Mean_W is the rolling mean and Std_W is the rolling standard deviation. The signal triggering logic operates as follows:
* **Short Spread (Z > Z_entry)**: Sell Stock A, Buy Stock B (Expect ratio to fall back to mean)
* **Long Spread (Z < -Z_entry)**: Buy Stock A, Sell Stock B (Expect ratio to bounce back to mean)
* **Hard Stop (|Z| >= Z_stop)**: Safeguards against cointegration breakdown (structural break).

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend & API Layer** | Python 3.13, FastAPI, SQLAlchemy |
| **Data Architecture** | PostgreSQL, pandas, numpy, statsmodels |
| **Ingestion Engine** | yfinance API, requests (Scraping Layer) |
| **Automation** | APScheduler (Advanced Python Scheduler) |
| **Frontend UI** | Jinja2 Templates, Tailwind CSS, Three.js (WebGL Shaders) |
| **Security Layer** | itsdangerous (Signed cookies), slowapi (Rate Limiting) |
| **Server Gateway** | Uvicorn |

---

## Project Directory Tree

alpha_quant_bot/
├── config/
│   ├── settings.py          # Environment-based configuration & fallback manager
│   ├── database.py          # SQLAlchemy engine & scoped session pooler
│   ├── risk_config.py       # Hardcoded mathematical risk boundaries
│   └── logging_config.py    # Centralized stream logging formatting & noise filter
├── core/
│   ├── signal_generator.py  # Cointegration screening, matrix alignment & Z-score engine
│   ├── health_score.py      # Fundamental corporate scoring filter (SQL analytics)
│   └── analytics.py         # Advanced quant performance metric calculator (Max DD, PF)
├── data_pipeline/
│   ├── yfinance_fetcher.py  # Data scraping, User-Agent masking, & rate-limited ingestion
│   └── scheduler.py         # APScheduler cron rules for market hours
├── execution/
│   └── execution_engine.py  # Transaction friction calculator & position management loop
├── logs/                    # Runtime pipeline logs (Auto-generated)
├── tests/                   # Target folder for future unit and integration testing
├── web_app/
│   ├── templates/           # Fully responsive semantic HTML templates
│   │   ├── dashboard.html   # Signal monitoring matrix
│   │   ├── login.html       # Secure timing-attack proof login gateway
│   │   └── positions.html   # Trade ledger audit log
│   └── app.py               # FastAPI middleware, global rate-limiters & auth routes
├── .env.example             # Template for secure environment injection
├── .gitignore               # Strict pipeline caching and database file lock lists
├── requirements.txt         # Package dependencies file
└── run_bot.py               # Main platform entry execution script

---

## Installation & Setup

### 1. Clone the Repository
git clone https://github.com/ardabaranbaytar/alpha-quant-bot.git
cd alpha-quant-bot

### 2. Install Dependencies
pip install -r requirements.txt

### 3. Configure Environment Variables
Copy the template environmental file and customize your secure credentials:
cp .env.example .env

Open .env and fill in your details:
DB_USER=postgres
DB_PASS=your_secure_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=financial_analysis

APP_USERNAME=admin
APP_PASSWORD=your_super_strong_dashboard_password
SESSION_SECRET=your_cryptographic_random_hex_secret

ALLOWED_ORIGINS=http://localhost:8000
LOG_LEVEL=INFO

### 4. Database Setup
The system automatically maps models. Ensure your target PostgreSQL database instance contains the following base target tables:
* `stock_prices` — Stores time-series historical market pricing vectors.
* `company_balance_sheets` — Houses scraped corporate health indices.
* `positions` — Audits long/short open and closed simulated position ledgers.

### 5. Launch the Platform
python run_bot.py

Open your browser and navigate to http://localhost:8000 to access the trading terminal.

---

## Quantitative Research Roadmap

- [ ] Integrate institutional data feeds (e.g., Bloomberg B-Pipe, Benzinga, or Alpaca) to substitute public web-scraping layers.
- [ ] Implement an event-driven backtesting framework incorporating walk-forward optimization and Monte Carlo simulations.
- [ ] Engineer a high-frequency low-latency execution wrapper in C++ to achieve direct market access (DMA) connectivity with brokers.
- [ ] Implement multi-factor alpha models (e.g., combining momentum and sentiment vectors with cointegration).

---

## License

Distributed under the MIT License. See LICENSE for more information.
