# Architecture

## System Flow

Two primary user-facing flows exist today (both start from CSV ingestion):

### A) Store/Campaign decision flow (production path)

1. Upload CSV (Streamlit `Home`)
2. Parse + persist orders/line items
3. `metrics_engine` → store-level computed metrics
4. `signal_engine` → signal events from metrics
5. `rules_engine` → matched rules
6. `narrative_engine` → merchant-facing insights (title/summary/implication/action)
7. `dashboard_service` + `campaign_insight_enricher` → ranked, money-oriented campaign insights
8. Streamlit `/Campaigns` renders: summary tables, risks, and top actions; PDF export is available (fallback when rich PDF deps are missing)

### B) SKU discount & promotion drafts (parallel path)

1. Upload CSV (same source of truth)
2. Aggregate per SKU from order line items (`discount_recommendation.py`)
3. Build `PromotionDraft` objects (`promotion_draft.py`)
   - Level 2: velocity + confidence + segment policy
   - Level 3: promotion mix templates (`campaign_type` + `campaign_template`)
4. Streamlit `/Discount` renders drafts with a review workflow (Accept/Reject/Adjust) and exports JSON; drafts can be persisted in DB for future execution adapters

## Core Loop

Explore → Execute → Measure → Learn → Optimize

## Output

- Campaign/categorized insights and actions (measured + proxy impact)
- SKU-level promotion drafts (JSON + DB persisted) for future execution

