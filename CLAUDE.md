# Startup Searcher

Pipeline that finds early-stage startups using public momentum signals,
researches top candidates with an AI agent, and tracks whether
predictions come true (e.g., raising a round within 12 months).

## Rules
- Use official APIs and public filings only. No scraping PitchBook,
  LinkedIn, Crunchbase, or sites that require login.
- Database is SQLite (startups.db). Snapshots are append-only:
  always INSERT with a snapshot_at timestamp, never UPDATE old rows.
- Secrets live in .env and are loaded with python-dotenv. Never hardcode keys.
- Respect API rate limits.
- Keep code simple and explain it; I'm learning as I build.