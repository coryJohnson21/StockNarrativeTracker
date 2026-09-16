# NarrativeTracker

Financial media intelligence platform — ingests CNBC clips, earnings calls, and finance videos, then identifies trending stocks, sectors, and investment themes with narrative momentum scoring.

## Architecture

```
Frontend (Next.js 14)     Backend (FastAPI)        Database
      │                         │                    │
  Dashboard ──────── REST ────► Ingest Router ──────► PostgreSQL
  Stocks Page                   Stocks Router          + pgvector
  Themes Page                   Themes Router
  Sources Page                  Sources Router
  Ingest Form                      │
                              AI Pipeline:
                              1. yt-dlp download
                              2. Whisper transcription
                              3. GPT-4o extraction
                              4. text-embedding-3-small
                              5. Momentum scoring
```

## Quick Start (Docker)

```bash
# 1. Clone and set up env
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY

# 2. Export key for docker-compose
export OPENAI_API_KEY=sk-...

# 3. Start everything
docker-compose up --build

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Local Development

### Backend

```bash
cd backend

# Install deps (requires Python 3.11+)
pip install -r requirements.txt

# Install ffmpeg (required for yt-dlp audio extraction)
brew install ffmpeg   # macOS
# apt install ffmpeg  # Ubuntu

# Copy and fill in env
cp .env.example .env
# Set DATABASE_URL and OPENAI_API_KEY

# Start PostgreSQL with pgvector (via Docker)
docker run -d \
  --name narrativetracker-db \
  -e POSTGRES_USER=narrativetracker \
  -e POSTGRES_PASSWORD=narrativetracker \
  -e POSTGRES_DB=narrativetracker \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Run migrations (or let FastAPI auto-create on startup)
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Migrations are the source of truth for the schema. The app also runs `Base.metadata.create_all` on startup as a dev convenience, but that only adds missing tables and never alters existing ones — every model change still needs a migration. If a database was bootstrapped by `create_all` alone (no `alembic_version` table), mark it as current before upgrading:

```bash
alembic stamp head
```

### Backend tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

### Frontend

```bash
cd frontend

# Install deps
npm install

# Copy env
cp .env.local.example .env.local

# Start dev server
npm run dev
# Open http://localhost:3000
```

## Database Schema

| Table | Description |
|-------|-------------|
| `sources` | YouTube videos and uploaded transcripts |
| `transcripts` | Full text + 1536-dim pgvector embedding |
| `stocks` | Unique tickers extracted across all sources |
| `themes` | Investment themes (AI, Nuclear, etc.) |
| `stock_mentions` | Per-source stock mentions with sentiment |
| `theme_mentions` | Per-source theme mentions with sentiment |
| `stock_momentum` | Computed momentum scores for stocks |
| `theme_momentum` | Computed momentum scores for themes |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ingest/youtube` | Submit YouTube URL for processing |
| POST | `/api/ingest/transcript` | Upload pre-transcribed text |
| GET | `/api/stocks/trending` | Trending stocks by momentum score |
| GET | `/api/stocks/{ticker}/mentions` | All mentions for a stock |
| GET | `/api/themes/trending` | Trending themes by momentum score |
| GET | `/api/themes/{name}/mentions` | All mentions for a theme |
| GET | `/api/sources` | List all ingested sources |
| DELETE | `/api/sources/{id}` | Delete a source and its data |
| GET | `/api/dashboard/stats` | Summary stats for dashboard |
| GET | `/api/stocks/{ticker}/calls` | Explicit buy/sell/hold calls made about a stock |
| POST | `/api/research/refresh` | Pull daily prices (+ SPY) and rebuild point-in-time momentum snapshots |
| GET | `/api/research/backtest` | Forward returns by score quintile and rank IC per factor (`horizon`, `buckets`, `min_mentions_7d`) |
| GET | `/api/research/status` | Snapshot and price coverage |

Full interactive docs at: `http://localhost:8000/docs`

## Momentum Score (0–100)

Scores are computed as a weighted combination:

| Factor | Weight | Description |
|--------|--------|-------------|
| Share of voice | 30% | Percentile rank of this entity's share of all mentions in the last 30 days — relative attention that doesn't inflate just because more sources were ingested that week |
| Growth | 30% | Last 7 days vs. the *preceding* 23 days (non-overlapping baseline), as a log-ratio shrunk toward "no change" with pseudo-counts so a single mention can't register as a spike |
| Sentiment | 25% | Mention-weighted average sentiment relative to the universe-wide average, shrunk toward neutral for small samples |
| Cross-source diversity | 15% | Unique sources mentioning this entity (saturates at 5) |

Self-mentions (a company discussed in its own filing) are down-weighted to 0.3 in every component. Each result also carries a `confidence` of `low` / `medium` / `high` derived from mention count and source diversity — treat `low` sentiment readings as anecdotes, not signals.

Scores refresh automatically after each source is processed, or on demand via `POST /api/ingest/refresh-momentum`.

## Does the score predict anything?

The Research page (`/research`) is the honest answer. `POST /api/research/refresh` pulls a year of daily closes for every tracked stock plus SPY, then rebuilds a **point-in-time** momentum snapshot for every stock-day since the first mention — each day's score uses only mentions published on or before that day. `GET /api/research/backtest?horizon=20` joins those snapshots to forward returns and reports:

- mean and median SPY-excess return by score quintile, with hit rate and the top-minus-bottom spread;
- the rank correlation (information coefficient) between forward return and the score and each of its components (sentiment, 7-day mentions, share of voice);
- the mean of per-day ICs and its t-stat, so a single lucky week can't carry a factor.

A positive, significant IC on sentiment means narrative leads price. A negative one means attention peaks late and the signal is contrarian. Treat anything under a few hundred observations across 20+ days as a hypothesis. With `ENABLE_AUTO_INGEST=true` the refresh runs daily.

## AI Pipeline

1. **Audio extraction** — `yt-dlp` downloads audio from YouTube at 64kbps MP3 (max 25MB for Whisper)
2. **Transcription** — OpenAI Whisper API converts audio to text
3. **Entity extraction** — GPT-4o in JSON mode extracts:
   - Stock tickers + company names + sentiment (-100 to +100)
   - Investment themes + sentiment + context
   - 2–3 sentence investment summary
4. **Embedding** — `text-embedding-3-small` generates 1536-dim vector stored in pgvector
5. **Momentum refresh** — Scores recomputed for all stocks/themes after each ingestion

## Deployment

### Vercel (Frontend)
```bash
cd frontend
vercel deploy
# Set NEXT_PUBLIC_API_URL to your Railway backend URL
```

### Railway (Backend)
1. Create a new Railway project
2. Add a PostgreSQL service and enable the pgvector extension
3. Deploy from `./backend` directory
4. Set `DATABASE_URL` and `OPENAI_API_KEY` environment variables
5. The `Dockerfile` handles ffmpeg installation

## Roadmap

### Phase 1 — MVP (current)
- [x] YouTube ingestion + Whisper transcription
- [x] GPT-4o entity extraction (stocks, themes, sentiment)
- [x] Momentum scoring algorithm
- [x] Trending stocks and themes dashboards
- [x] Source management with status tracking

### Phase 2 — Growth
- [ ] Bulk YouTube playlist/channel ingestion
- [ ] Scheduled re-scoring (cron)
- [ ] Email/Slack alerts for momentum spikes
- [ ] Semantic search across transcripts (pgvector)
- [ ] Per-ticker detail page with mention history chart

### Phase 3 — Scale
- [ ] Celery + Redis for async job queue
- [ ] Multi-user with auth
- [ ] Custom watchlists
- [ ] Export to CSV/PDF
- [ ] API rate limiting and usage tracking
# StockNarrativeTracker
