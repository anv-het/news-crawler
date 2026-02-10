# Investor Crawler - Scrapy Framework Project Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Data Flow](#data-flow)
5. [Anti-Ban & CAPTCHA Strategy](#anti-ban--captcha-strategy)
6. [Data Pipeline](#data-pipeline)
7. [Configuration](#configuration)
8. [Output Format](#output-format)
9. [Usage](#usage)
10. [Comparison: Plain Python vs Scrapy](#comparison)

---

## Project Overview

A **Scrapy framework** based web crawler that:
1. **Searches** DuckDuckGo for investor relations queries
2. **Collects** top 15-20 first-page URLs from search results
3. **Visits** the top 3 URLs using Scrapy's async engine + middlewares
4. **Detects** and handles CAPTCHAs, Cloudflare challenges, rate-limiting
5. **Extracts** all hyperlinks + document links (PDF, XLSX, CSV, PPT, DOC)
6. **Saves** structured results to JSON, CSV, and MongoDB via Scrapy pipelines

### Why Scrapy Framework?

| Feature | Plain Python (scrapy/ dir) | Scrapy Framework (crawler/ dir) |
|---------|---------------------------|----------------------------------|
| Async requests | ❌ Sequential | ✅ Twisted async engine |
| CAPTCHA detection | ❌ None | ✅ Middleware-based |
| Rotating User-Agent | ❌ Single UA | ✅ Pool of 14 UAs |
| Auto throttling | ❌ Manual | ✅ Built-in AutoThrottle |
| Retry logic | ❌ None | ✅ Retry middleware |
| Browser-like headers | ❌ Basic | ✅ Full Sec-Fetch headers |
| Pipeline architecture | ❌ Manual | ✅ Scrapy Item Pipelines |
| Error handling | ❌ Try/catch | ✅ errback + middleware |
| Concurrent crawling | ❌ Sequential | ✅ Configurable concurrency |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    main.py (Entry Point)                             │
│    Loads Scrapy settings → CrawlerProcess → investor_spider          │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   Scrapy Engine (Twisted Reactor)                     │
│                                                                      │
│  ┌─────────────┐   ┌──────────────────┐   ┌───────────────────┐     │
│  │  Scheduler   │   │  Downloader       │   │  Spider            │     │
│  │  (Queue)     │──▶│  + Middlewares     │──▶│  investor_spider   │     │
│  └─────────────┘   └──────────────────┘   └───────────────────┘     │
│                                                                      │
│  DOWNLOADER MIDDLEWARES (executed on every request/response):        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ 400: RotatingUserAgentMiddleware  ← Random UA per request   │    │
│  │ 450: CaptchaDetectionMiddleware   ← Detect & retry CAPTCHA  │    │
│  │ 500: LongDelayMiddleware          ← Long break every 30 req │    │
│  │ 550: RandomHeadersMiddleware      ← Browser-like headers    │    │
│  │ 600: RetryMiddleware (built-in)   ← Retry on 403/429/5xx   │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      ITEM PIPELINES                                   │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐          │
│  │ 100: JSON     │  │ 200: CSV     │  │ 300: MongoDB      │          │
│  │ Pipeline      │  │ Pipeline     │  │ Pipeline          │          │
│  │              │  │              │  │                   │          │
│  │ DATA/JSON/   │  │ DATA/CSV/    │  │ WEB_CRAWLER DB    │          │
│  │ <query>/     │  │ <query>/     │  │ invester_rel...   │          │
│  └──────────────┘  └──────────────┘  └───────────────────┘          │
│                                                                      │
│  Each pipeline controlled by SAVE_TO_* switches in .env              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
crawler/                              # Project root
│
├── .env                              # All configuration (switches, creds, delays)
├── requirements.txt                  # Python dependencies
├── scrapy.cfg                        # Scrapy project config
├── main.py                           # CLI entry point (python main.py)
├── queries.csv                       # Input queries (one per line)
│
├── investor_crawler/                 # Scrapy project package
│   ├── __init__.py
│   ├── settings.py                   # Scrapy settings (loads .env)
│   ├── items.py                      # CrawlResultItem definition
│   ├── pipelines.py                  # JSON / CSV / MongoDB pipelines
│   ├── middlewares.py                # Anti-ban / CAPTCHA / UA rotation
│   └── spiders/
│       ├── __init__.py
│       └── investor_spider.py        # Main spider (DDG → crawl → extract)
│
├── DATA/                             # Output data
│   ├── CSV/                         # <query_folder>/<query>_<datetime>.csv
│   └── JSON/                        # <query_folder>/<query>_<datetime>.json
│
├── logs/                             # scrapy_crawler_<datetime>.log
│
└── DOCS/
    └── PROJECT_DOCUMENTATION.md      # This file
```

---

## Data Flow

```
INPUT: queries.csv
  ┌───────────────────────────────┐
  │ reliance investor relations   │
  │ tcs news                      │
  │ infosys shareholding          │
  └──────────┬────────────────────┘
             │
             ▼
STEP 1: DUCKDUCKGO SEARCH (inside spider)
  ┌──────────────────────────────────────────────────────┐
  │ ddgs.text("reliance investor relations", max=20)     │
  │ → Returns 15-20 search result URLs                   │
  │   [{title, url, snippet}, ...]                       │
  └──────────┬───────────────────────────────────────────┘
             │
             ▼
STEP 2: SELECT TOP 3 URLs
  ┌──────────────────────────────────────────────────────┐
  │ Top 3 URLs → yield scrapy.Request() for each         │
  │                                                      │
  │ Request flows through MIDDLEWARES:                    │
  │   → RotatingUserAgentMiddleware (random UA)           │
  │   → RandomHeadersMiddleware (Sec-Fetch, Accept, etc.) │
  │   → LongDelayMiddleware (pause every 30 requests)    │
  │   → Scrapy's AutoThrottle (adaptive delay)           │
  └──────────┬───────────────────────────────────────────┘
             │
             ▼
STEP 3: CRAWL EACH PAGE (parse_top_url callback)
  ┌──────────────────────────────────────────────────────┐
  │ Response flows through:                              │
  │   → CaptchaDetectionMiddleware                       │
  │     If CAPTCHA detected → retry with new UA & delay   │
  │                                                      │
  │ Spider extracts:                                     │
  │   → css("title::text")       → page title            │
  │   → css("a::attr(href)")     → ALL links             │
  │   → filter doc extensions    → doc links             │
  │     (.pdf .xlsx .csv .ppt .doc .docx .zip .rar .txt) │
  └──────────┬───────────────────────────────────────────┘
             │
             ▼
STEP 4: BUILD ITEM & SAVE (Pipelines)
  ┌──────────────────────────────────────────────────────┐
  │ When all 3 pages crawled:                            │
  │   → Build CrawlResultItem                            │
  │   → yield item                                       │
  │                                                      │
  │ Pipelines process item:                              │
  │   100: JsonFilePipeline  → DATA/JSON/<query>/        │
  │   200: CsvFilePipeline   → DATA/CSV/<query>/         │
  │   300: MongoDBPipeline   → WEB_CRAWLER collection    │
  └──────────────────────────────────────────────────────┘
```

---

## Anti-Ban & CAPTCHA Strategy

### 1. Rotating User Agents
Pool of **14 realistic browser User-Agents** (Chrome, Firefox, Edge, Safari)
across Windows, macOS, and Linux. A random UA is selected per request.

### 2. CAPTCHA Detection
Scans response body (first 5KB) for indicators:
- `captcha`, `recaptcha`, `hcaptcha`, `cf-challenge`, `cf-turnstile`
- `are you a robot`, `verify you are human`, `access denied`
- `cloudflare`, `checking your browser`, `just a moment`
- `unusual traffic`, `bot detection`, `ray id`

On detection:
- Waits 5-15 seconds (increasing with each retry)
- Retries with a different User-Agent
- Up to MAX_RETRIES (default: 3) attempts

### 3. AutoThrottle
Scrapy's built-in intelligent throttling:
- Automatically adjusts delay based on server response times
- Starts at 2s, max 10s, targets 1.0 concurrency
- Prevents overwhelming slow servers

### 4. Long Delay Breaks
After every 30 requests, takes a 10-15 second pause
to mimic human browsing patterns.

### 5. Browser-Like Headers
Every request includes:
- `Accept`, `Accept-Language`, `Accept-Encoding`
- `Sec-Fetch-Dest`, `Sec-Fetch-Mode`, `Sec-Fetch-Site`
- `Upgrade-Insecure-Requests`, `Cache-Control`
- Randomized `Accept-Language` variants

### 6. Retry on Failures
Built-in Scrapy retry on HTTP codes: 403, 408, 429, 500, 502, 503, 504

---

## Configuration

All settings in `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `SEARCH_ENGINE` | duckduckgo | Search engine |
| `MAX_SEARCH_RESULTS` | 20 | Results per query |
| `TOP_URLS_TO_VISIT` | 3 | URLs to deep-crawl |
| `SAVE_TO_JSON` | true | JSON output switch |
| `SAVE_TO_CSV` | true | CSV output switch |
| `SAVE_TO_MONGO` | true | MongoDB output switch |
| `MONGO_URI` | mongodb://... | MongoDB connection |
| `CONCURRENT_REQUESTS` | 4 | Parallel requests |
| `AUTOTHROTTLE_ENABLED` | true | Smart delay |
| `ROTATING_USER_AGENT` | true | Random UA per request |
| `CAPTCHA_DETECTION` | true | Detect CAPTCHA pages |
| `RETRY_ON_CAPTCHA` | true | Retry on CAPTCHA |
| `MAX_RETRIES` | 3 | Max CAPTCHA retries |

---

## Usage

```bash
# All queries from queries.csv
python main.py

# Single query
python main.py --query "reliance investor relations"

# Custom queries file
python main.py --file custom.csv

# Using scrapy directly
scrapy crawl investor_spider
scrapy crawl investor_spider -a query="tcs news"
```

---

## Output Example

After running `python main.py -q "reliance investor relations"`:

```
DATA/
├── CSV/
│   └── reliance_investor_relations/
│       └── reliance_investor_relations_20260210_180000.csv
├── JSON/
│   └── reliance_investor_relations/
│       └── reliance_investor_relations_20260210_180000.json

logs/
└── scrapy_crawler_20260210_180000.log

MongoDB: WEB_CRAWLER.invester_relation_scrapy → document inserted
```
