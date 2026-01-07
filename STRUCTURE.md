# Project Structure

This document describes the project layout, the main runtime flow, and how the core
components fit together. It is intended as a quick orientation map.

## Top-Level Layout

- `main.py`: FastAPI app entry point, routing setup, static/template mounting, and
  lifecycle hooks (startup/shutdown).
- `config.yaml.template`: Config template for runtime settings.
- `config.yaml`: Runtime config (local, not committed).
- `aibangumi.db`: Local SQLite database (runtime data).

## App Directories

- `api/`: FastAPI route handlers (auth, sources, torrents, users, cache).
- `core/`: Core business logic (scheduler, source access, auth helpers, config).
- `models/`: SQLAlchemy models, async session setup, and Base definitions.
- `schemas/`: Pydantic request/response models for API payloads.
- `utils/`: External integrations and helper modules (RSS, TMDB, qBittorrent, LLM, magnet, DHT).
- `templates/`: Server-rendered HTML templates (main page, auth, source pages).
- `static/`: Frontend assets (CSS/JS).

## Runtime Flow (High Level)

1. `main.py` starts FastAPI with a lifespan handler.
2. On startup:
   - Initialize the database tables.
   - Start the scheduler loop.
   - Start the DHT service.
3. The scheduler loop:
   - Fetches RSS or magnet sources.
   - Creates torrent records as needed.
   - Adds torrents to qBittorrent.
   - Tracks download progress.
   - Processes completed torrents into File records and hardlinks.
4. API routes expose CRUD and operational actions to the UI.

## Data Model Relationships

- `Source` -> `Torrent` -> `File`
- Deletions cascade from `Source` to `Torrent` to `File`.

## Key Modules

- `core/config.py`: Loads and validates runtime config.
- `core/scheduler.py`: Periodic processing for RSS/magnet sources and download workflow.
- `core/user.py`: Password hashing, JWT generation, and auth helpers.
- `utils/ai.py`: Title cleanup, regex generation, and episode/file analysis using LLM.
- `utils/rss.py`: RSS/Atom fetching and parsing.
- `utils/magnet.py`: Torrent conversion, metadata extraction, and caching.
- `utils/qbittorrent.py`: qBittorrent Web API integration.
- `utils/tmdb.py`: TMDB search and TV details.
- `utils/dht.py`: DHT metadata fetch service.

## Notes

- If you adjust API contracts, update `schemas/` and the frontend assets in `static/`.
- `config.yaml` is required at runtime; keep secrets out of version control.
