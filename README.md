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

Full interactive docs at: `http://localhost:8000/docs`

## Momentum Score (0–100)

Scores are computed as a weighted combination:

| Factor | Weight | Description |
|--------|--------|-------------|
| Mention frequency | 30% | Normalized total mentions |
| Growth rate | 30% | Recent 7d vs prior 30d trend |
| Sentiment | 25% | Avg sentiment (-100 to +100) → normalized |
| Cross-source diversity | 15% | Unique sources mentioning this entity |

Scores refresh automatically after each source is processed.

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
