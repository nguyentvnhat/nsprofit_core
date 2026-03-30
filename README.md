# NosaProfit (MVP)

Production-minded analytics MVP for Shopify order exports: ingest CSV → normalize → MySQL → metrics → signals → YAML rules → deterministic narratives → Streamlit.

## Product

See `docs/product.md` for product vision, mission, and scope.

## Layout

- **`app/`** — Core application: config, DB, ORM models, repositories, services (no Streamlit business logic).
- **`streamlit_app/`** — Thin UI that calls `app.services.dashboard_service` and pipeline helpers.
- **`tests/`** — Unit tests (expand as you grow).
- **`migrations/`** — Alembic revision history (run `alembic upgrade head` after configuring `alembic.ini`).

## Quick start

1. Create a MySQL database and a `.env` file (see `.env.example` if present, or set variables below).

2. Install dependencies:

```bash
cd nosaprofit
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Set environment variables:

```bash
export NOSAPROFIT_DATABASE_URL="mysql+pymysql://user:pass@127.0.0.1:3306/nosaprofit"
export NOSAPROFIT_RULES_DIR="./app/rules"   # optional; defaults relative to package
```

4. Create tables (MVP bootstrap):

```bash
export PYTHONPATH=.
python -m app.main init-db
```

5. Run Streamlit:

```bash
streamlit run streamlit_app/Home.py
```

## Architecture notes

- **Models** — SQLAlchemy ORM entities only.
- **Repositories** — Persistence boundaries; services use these, not raw SQL in UI.
- **Services** — Parsing, normalization, `metrics_engine`, `signal_engine`, `rules_engine`, `narrative_engine`, `dashboard_service`.
- **Rules** — YAML under `app/rules/`; evaluated by `rules_engine.py` (no hardcoded thresholds in Streamlit).
- **Future** — Swap Streamlit for FastAPI by exposing the same service layer; add `tenant_id` to models when moving to multi-tenant SaaS.

## Extending

- **New metric**: Add a module under `app/services/metrics_engine/` and register in `metrics_engine/__init__.py`.
- **New signal**: Add under `app/services/signal_engine/` and register in `signal_engine/__init__.py`.
- **New rule**: Edit or add YAML in `app/rules/`; optional sync into `rule_definitions` for audit.
