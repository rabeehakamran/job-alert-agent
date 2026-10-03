# Job Alert Agent

An agentic pipeline that filters job/internship alert emails (LinkedIn, Indeed,
JobRight, etc.) down to a daily digest of roles that actually fit, instead of
scrolling through dozens of irrelevant alerts scattered across platforms.

## Why

Job-seeking candidates end up subscribed to multiple platforms, each sending
their own alert emails -- most of which aren't relevant (wrong seniority,
wrong stack, wrong domain). This project automates the filtering: pull the
alerts, extract structured job data, score relevance against a candidate
profile, and deliver only the good matches.

## Pipeline

```
Gmail inbox (daily cron poll)
   -> Extraction agent       (Groq LLM: raw email -> structured JSON)
   -> Embedding filter       (coarse relevance vs. candidate profile)
   -> LLM judge               (fine-grained score + reasoning + seniority check)
   -> Supabase                (dedup + storage)
   -> WhatsApp digest         (Twilio: daily summary of top matches)
```

Design notes:
- Gmail polling uses a simple `newer_than:1d` query rather than incremental
  `historyId` sync -- for a daily digest, a missed email just shows up a day
  late, so the simpler approach's failure mode is harmless.
- Scoring is a two-stage hybrid: a cheap embedding similarity pass filters
  out obvious mismatches first, then an LLM judge only runs on what's left,
  giving nuanced scoring (e.g. catching "AI Engineer, 5+ years" as a
  seniority mismatch even when the stack matches) with a human-readable
  reasoning line for the digest.

## Project structure

```
job-alert-agent/
├── gmail_ingest/        # Stage 1: fetch + parse job-alert emails
│   ├── auth.py          # OAuth login, token persistence
│   ├── fetch.py         # query + fetch messages
│   └── parser.py        # recursive plain-text extraction, HTML fallback
├── extraction/          # Stage 2: LLM extraction to structured JSON
│   └── extract.py
├── scoring/              # Stage 3: embedding filter + LLM judge (in progress)
├── storage/              # Stage 4: Supabase dedup + storage (in progress)
├── delivery/              # Stage 5: Twilio WhatsApp digest (in progress)
├── run_ingest_and_extract.py   # manual test runner for stages 1-2
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup

### 1. Clone and install

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
python -m pip install -r requirements.txt
```

### 2. Gmail API credentials

1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **Gmail API**
3. Configure the OAuth consent screen (Google Auth Platform) as **External**,
   and add your own Gmail address under the **Audience** tab as a test user
4. Create an OAuth client ID (**Desktop app** type), download the JSON, save
   it as `credentials.json` in the project root
5. Run `python -m gmail_ingest.auth` once -- this opens a browser for the
   one-time login and saves `token.pickle` for future automatic runs

### 3. Environment variables

Copy `.env.example` to `.env` and fill in:

```
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.pickle
GROQ_API_KEY=your_groq_api_key_here
```

Get a free Groq API key at [console.groq.com](https://console.groq.com) --
no card required.

### 4. Run

```bash
python -m gmail_ingest.fetch           # test Gmail fetching alone
python -m run_ingest_and_extract       # test fetch + extraction together
```

> Note: files inside a package (e.g. `gmail_ingest/fetch.py`) must be run
> with `python -m package.module`, not `python package/module.py` --
> otherwise their internal `from gmail_ingest.x import y` imports won't
> resolve.

## Current status

- [x] Gmail ingestion -- fetches and parses job-alert emails
- [x] Extraction agent -- converts raw emails to structured job JSON (Groq,
      `openai/gpt-oss-20b`)
- [ ] Embedding filter -- coarse relevance scoring against resume/profile
- [ ] LLM judge -- fine-grained scoring + reasoning
- [ ] Supabase storage -- dedup + persistence
- [ ] WhatsApp digest -- daily delivery via Twilio

## Known limitations

- Long digest emails (15+ bundled job listings) get truncated at 8,000
  characters before extraction, so not every listing in a very long digest
  is captured yet.
- Twilio WhatsApp sandbox requires re-joining every 24 hours (a trial-tier
  limitation); a production number removes this once the project is ready
  to move off sandbox.

## Stack

Python, Gmail API, Groq (LLM inference), Supabase (pgvector), Twilio
(WhatsApp), deployed on Render/Railway.
