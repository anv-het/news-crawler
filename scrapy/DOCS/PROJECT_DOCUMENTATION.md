# Web Crawler - Project Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Data Flow](#data-flow)
5. [Data Pipeline](#data-pipeline)
6. [Configuration](#configuration)
7. [Output Format](#output-format)
8. [Usage](#usage)

---

## Project Overview

A Python-based web crawler that:
1. **Searches** DuckDuckGo for investor relations queries
2. **Collects** top 15-20 first-page URLs from search results
3. **Visits** the top 3 URLs and extracts all hyperlinks
4. **Identifies** document links (PDF, XLSX, CSV, PPT, DOCX, etc.)
5. **Saves** structured results to JSON, CSV, and MongoDB

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAIN.PY (Orchestrator)                    │
│  Reads queries.csv → loops through each query → triggers flow    │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────┐
│   CONFIG / SETTINGS   │  ← Loads .env file
│  (config/settings.py) │  ← All switches, delays, paths, creds
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                         CORE MODULES                              │
│                                                                    │
│  ┌─────────────────┐   ┌──────────────────┐                      │
│  │  SEARCHER        │   │  PAGE CRAWLER     │                      │
│  │  (DuckDuckGo)    │──▶│  (Visit top URLs) │                      │
│  │                  │   │  Extract links    │                      │
│  │  Query →         │   │  Extract doc URLs │                      │
│  │  15-20 URLs      │   │  (pdf,xlsx,csv..) │                      │
│  └─────────────────┘   └──────────────────┘                      │
│                                                                    │
│  ┌──────────────────┐                                             │
│  │  DELAY MANAGER    │  ← Random delays between requests          │
│  │  Normal: 1-3s     │  ← Long delay every 30 requests: 10-15s   │
│  └──────────────────┘                                             │
└──────────┬───────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                       DATA PIPELINE                               │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐        │
│  │  JSON SAVER   │  │  CSV SAVER   │  │  MONGODB SAVER   │        │
│  │              │  │              │  │                  │        │
│  │ DATA/JSON/   │  │ DATA/CSV/    │  │ WEB_CRAWLER DB   │        │
│  │ query_folder/ │  │ query_folder/ │  │ invester_rel..  │        │
│  │  file.json   │  │  file.csv    │  │  collection     │        │
│  └──────────────┘  └──────────────┘  └──────────────────┘        │
│                                                                    │
│  Each saver has a SWITCH (SAVE_TO_JSON, SAVE_TO_CSV, etc.)        │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                         LOGGING                                    │
│  Console output + File logging (logs/scraper_DATETIME.log)        │
│  Configurable: LOG_ENABLED, LOG_LEVEL, LOG_TO_FILE, LOG_TO_CONSOLE│
└──────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
scrapy/
│
├── .env                          # All configuration switches & credentials
├── requirements.txt              # Python dependencies
├── main.py                       # Entry point - orchestrates the full flow
├── queries.csv                   # Input: one search query per line
│
├── config/                       # Configuration package
│   ├── __init__.py              # Exports Settings instance
│   └── settings.py              # Loads .env → Python object
│
├── core/                         # Core logic
│   ├── __init__.py
│   ├── searcher.py              # DuckDuckGo search module
│   └── crawler.py               # Page visitor + link extractor
│
├── pipeline/                     # Data saving pipeline
│   ├── __init__.py
│   ├── json_saver.py            # Save to JSON files
│   ├── csv_saver.py             # Save to CSV files
│   └── mongo_saver.py           # Save to MongoDB
│
├── utils/                        # Utility modules
│   ├── __init__.py
│   ├── logger.py                # Logging setup (file + console)
│   └── delay.py                 # Request delay management
│
├── DATA/                         # Output data directory
│   ├── CSV/                     # CSV outputs (query_folder/file.csv)
│   └── JSON/                    # JSON outputs (query_folder/file.json)
│
├── logs/                         # Log files directory
│
└── DOCS/                         # Documentation
    └── PROJECT_DOCUMENTATION.md  # This file
```

---

## Data Flow

### Step-by-Step Process

```
INPUT: queries.csv
  ┌──────────────────────────────┐
  │ reliance investor relations  │
  │ tcs news                     │
  │ infosys shareholding         │
  │ ...                          │
  └──────────┬───────────────────┘
             │
             ▼
STEP 1: SEARCH (DuckDuckGo)
  ┌──────────────────────────────────────────────────┐
  │ Query: "reliance investor relations"             │
  │ → Returns 15-20 search result URLs               │
  │                                                  │
  │ Results:                                         │
  │   1. https://www.ril.com/investor-relations      │
  │   2. https://www.moneycontrol.com/...            │
  │   3. https://www.bseindia.com/...                │
  │   4. ... (up to 20 results)                      │
  └──────────┬───────────────────────────────────────┘
             │
             ▼
STEP 2: SELECT TOP 3 URLs
  ┌──────────────────────────────────────────────────┐
  │ Top 3 selected for deep crawling:                │
  │   1. https://www.ril.com/investor-relations      │
  │   2. https://www.moneycontrol.com/...            │
  │   3. https://www.bseindia.com/...                │
  └──────────┬───────────────────────────────────────┘
             │
             ▼
STEP 3: CRAWL EACH TOP URL
  ┌──────────────────────────────────────────────────┐
  │ For each URL:                                    │
  │   → Visit the page                              │
  │   → Extract ALL <a href="..."> links             │
  │   → Identify document links:                    │
  │     .pdf, .xlsx, .xls, .csv, .ppt, .pptx,      │
  │     .doc, .docx, .zip, .rar, .txt               │
  │                                                  │
  │ URL #1: ril.com/investor-relations               │
  │   → 150 links found                             │
  │   → 12 document links (annual-report.pdf, etc.)  │
  │                                                  │
  │ URL #2: moneycontrol.com/...                     │
  │   → 200 links found                             │
  │   → 3 document links                            │
  │                                                  │
  │ URL #3: bseindia.com/...                         │
  │   → 80 links found                              │
  │   → 5 document links                            │
  └──────────┬───────────────────────────────────────┘
             │
             ▼
STEP 4: SAVE (via Pipeline)
  ┌──────────────────────────────────────────────────┐
  │ JSON → DATA/JSON/reliance_investor_relations/    │
  │        reliance_investor_relations_20260210.json │
  │                                                  │
  │ CSV  → DATA/CSV/reliance_investor_relations/     │
  │        reliance_investor_relations_20260210.csv  │
  │                                                  │
  │ MongoDB → WEB_CRAWLER.invester_relation_scrapy   │
  │           (document inserted)                    │
  └──────────────────────────────────────────────────┘
```

---

## Data Pipeline

### JSON Output Structure

```json
{
  "query": "reliance investor relations",
  "timestamp": "2026-02-10T14:30:00",
  "search_results": [
    {
      "title": "Reliance Industries - Investor Relations",
      "url": "https://www.ril.com/investor-relations",
      "snippet": "Welcome to Reliance investor relations..."
    },
    // ... 15-20 more results
  ],
  "top_sites_crawled": [
    {
      "rank": 1,
      "url": "https://www.ril.com/investor-relations",
      "search_title": "Reliance Industries - Investor Relations",
      "page_title": "Investor Relations | RIL",
      "status": 200,
      "all_links": [
        "https://www.ril.com/about",
        "https://www.ril.com/annual-report",
        // ... all links from the page
      ],
      "doc_links": [
        "https://www.ril.com/docs/annual-report-2025.pdf",
        "https://www.ril.com/docs/quarterly-results.xlsx",
        // ... document links only
      ],
      "total_links_count": 150,
      "doc_links_count": 12
    },
    {
      "rank": 2,
      // ... second URL data
    },
    {
      "rank": 3,
      // ... third URL data
    }
  ],
  "stats": {
    "total_search_results": 20,
    "sites_crawled": 3,
    "total_links_found": 430,
    "total_doc_links_found": 20
  }
}
```

### CSV Output Structure

| query | rank | visited_url | page_title | link_type | link_url |
|-------|------|-------------|------------|-----------|----------|
| reliance investor relations | | https://ril.com/... | Reliance... | search_result | https://... |
| reliance investor relations | 1 | https://ril.com/... | Investor... | page_link | https://... |
| reliance investor relations | 1 | https://ril.com/... | Investor... | doc_link | https://.../report.pdf |

### MongoDB Document

Same structure as JSON, with additional fields:
- `_id`: Auto-generated ObjectId
- `created_at`: UTC timestamp
- `query_normalized`: Lowercase trimmed query

---

## Configuration

All settings are in the `.env` file:

| Setting | Default | Description |
|---------|---------|-------------|
| `SEARCH_ENGINE` | duckduckgo | Search engine to use |
| `MAX_SEARCH_RESULTS` | 20 | Number of search results to fetch |
| `TOP_URLS_TO_VISIT` | 3 | How many top URLs to deep-crawl |
| `SAVE_TO_JSON` | true | Enable/disable JSON saving |
| `SAVE_TO_CSV` | true | Enable/disable CSV saving |
| `SAVE_TO_MONGO` | true | Enable/disable MongoDB saving |
| `MONGO_URI` | mongodb://... | MongoDB connection string |
| `MONGO_DATABASE` | WEB_CRAWLER | MongoDB database name |
| `MONGO_COLLECTION` | invester_relation_scrapy | MongoDB collection name |
| `DELAY_MIN` | 1 | Min seconds between requests |
| `DELAY_MAX` | 3 | Max seconds between requests |
| `LONG_DELAY_MIN` | 10.0 | Min seconds for long break |
| `LONG_DELAY_MAX` | 15.0 | Max seconds for long break |
| `LONG_DELAY_AFTER_COUNT` | 30 | Take long break after N requests |
| `LOG_ENABLED` | true | Enable/disable logging |
| `LOG_LEVEL` | INFO | Log level (DEBUG/INFO/WARNING/ERROR) |
| `LOG_TO_FILE` | true | Write logs to file |
| `LOG_TO_CONSOLE` | true | Print logs to console |

---

## Usage

### Run all queries from queries.csv
```bash
python main.py
```

### Run a single query
```bash
python main.py --query "reliance investor relations"
```

### Use a custom queries file
```bash
python main.py --file custom_queries.csv
```

### Quick Test (single query)
```bash
python main.py -q "tcs news"
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `duckduckgo-search` | DuckDuckGo search API |
| `requests` | HTTP requests for page crawling |
| `beautifulsoup4` | HTML parsing and link extraction |
| `pymongo` | MongoDB driver |
| `python-dotenv` | Load .env configuration |
| `lxml` | Fast HTML parser for BeautifulSoup |

---

## Anti-Blocking Strategy

1. **Random delays** (1-3 seconds) between every request
2. **Long breaks** (10-15 seconds) after every 30 requests
3. **Realistic User-Agent** header mimicking Chrome browser
4. **Session-based requests** with proper Accept headers
5. **Timeout handling** to avoid hanging on slow sites
6. **Graceful error handling** - continues with next URL on failure

---

## Directory Output Example

After running with queries from `queries.csv`:

```
DATA/
├── CSV/
│   ├── reliance_investor_relations/
│   │   └── reliance_investor_relations_20260210_143000.csv
│   ├── tcs_news/
│   │   └── tcs_news_20260210_143500.csv
│   └── infosys_shareholding/
│       └── infosys_shareholding_20260210_144000.csv
├── JSON/
│   ├── reliance_investor_relations/
│   │   └── reliance_investor_relations_20260210_143000.json
│   ├── tcs_news/
│   │   └── tcs_news_20260210_143500.json
│   └── infosys_shareholding/
│       └── infosys_shareholding_20260210_144000.json
```
