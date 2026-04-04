# Discount recommendation & promotion drafts

This document describes the **SKU-level discount recommendation** path, the **promotion draft** contract for future **Shopify** (or other) execution, and a **five-level roadmap** for evolving the engine. Revisit this file when wiring Admin API create-after-click.

---

## 1) How this relates to the main pipeline

The store-level chain remains:

`metrics_engine` → `signal_engine` → `rules_engine` → `narrative_engine` (see [decision-flow.md](decision-flow.md)).

**Discount recommendation today does not consume** persisted metrics snapshots, YAML rules, `signal_events`, or `insights` from that chain. It recomputes from **order line items** via `OrderRepository` (same raw source as ingestion).

| Layer | Used by discount recommendation today? |
|--------|----------------------------------------|
| Metrics DB (`metric_snapshots`) | No |
| Signals / rules / insights | No |
| Line items (`net_line_revenue`, `line_discount_amount`, …) | Yes |

**Future improvement:** feed SKU metrics, entity-scoped signals, and rules so recommendations are auditable alongside other NosaProfit outputs.

---

## 2) Current modules (MVP / Level 1)

| Module | Role |
|--------|------|
| `app/services/discount_recommendation.py` | Aggregate per `(sku, product_name)`; compute discount share vs proxy pre-discount value; suggested simple promo %; margin **proxy** bands (no COGS). |
| `app/services/promotion_draft.py` | Frozen **`PromotionDraft`** objects + `schema_version`; JSON-serializable; maps from recommendation rows. |
| `app/integration/shopify_discounts.py` | **Stub** only: env flag, `build_shopify_discount_graphql_variables()` placeholder; **no HTTP/GraphQL** to Shopify. |
| `streamlit_app/pages/8_Discount.py` | UI + table + **duration** slider + **JSON export** of drafts + optional GraphQL placeholder preview. |
| `app/models/promotion_draft.py` | ORM model for persisted drafts (`promotion_drafts` table). |
| `app/repositories/promotion_draft_repository.py` | Replace/list drafts for an upload. |

Design references:

- Promo depth ceiling aligns in spirit with `_TARGET_DISCOUNT_RATE` (`0.15`) in `campaign_insight_enricher.py` (same idea, separate constant in `discount_recommendation.py`).
- **Campaigns** page (`7_Campaigns.py`): bucket-level **discount ÷ gross** and risks; **not** the same as per-SKU promo suggestions.

### 2.1 Proxy pre-discount line value

For each SKU aggregate:

- `pre_tot ≈ net_line_revenue_total + line_discount_total`
- `current_discount_pct = line_discount_total / pre_tot` (clamped)
- `value_retained_pct = (1 - share) × 100`

**Not** accounting gross margin: there is no `unit_cost` on `OrderItem`.

### 2.2 `PromotionDraft` contract

- **`schema_version`**: bump when fields or semantics change (consumers / API branching).
- **`level`**: roadmap stage (`1` = basic % MVP).
- **`source`**: e.g. `discount_recommendation_heuristic_v1`.
- **`rationale_codes`**: short tags for traceability (`line_item_economics`, `headroom_heuristic`, …).

Export: JSON array from `promotion_drafts_to_jsonable(...)`.

### 2.2.1 Persisting drafts to DB (recommended for portal + execution)

Drafts can be saved to the database (per upload) to support:

- auditability (what was suggested at the time),
- approval workflows (`draft` → `approved` → `published`),
- one-click execution later (Shopify adapter reads persisted drafts),
- decoupling UI from recomputation.

Table: `promotion_drafts` (created by Alembic revision `20260330_01`).

Current behavior in Streamlit:

- `Save drafts to DB` replaces drafts for the given `upload_id` (like insights do).

### 2.3 Shopify integration (future)

| Setting | Meaning |
|---------|--------|
| `NOSAPROFIT_SHOPIFY_DISCOUNT_INTEGRATION_ENABLED` | `false` by default. When `true`, future code may call a real Admin API client; **today** `create_shopify_discount()` still raises `NotImplementedError` if invoked after enabling. |

Placeholder payload: `build_shopify_discount_graphql_variables(draft)` — stable JSON shape for implementation (title, percentage, window, SKU list, empty `merchandise_ids_gql` until catalog GIDs exist).

---

## 3) Five-level engine roadmap (focus for improvements)

Work **level by level**: add one primary data source or decision type per stage; keep a single recommendation core that outputs **`PromotionDraft`** (extend fields as needed).

### Level 1 — Basic discount recommendation (MVP baseline)

- **Output:** simple %, product (SKU), duration (human-chosen or default).
- **Logic:** sales history + line discount heuristics; label gaps honestly (no fake conversion/inventory if missing).
- **Posture:** human decides, system suggests.

**Improvements here:** tighter heuristics, tie-breakers, caps by catalog tier, link `rationale_codes` to store-level signals when available.

### Level 2 — Contextual discount

- **Add:** *who / when / what* — light segments first (e.g. new vs returning vs unknown; slow/fast movers as **proxies** from order velocity unless inventory sync exists).
- **Output:** drafts carry `segment_policy`, `velocity_bucket`, `units_7d`, `units_30d`, `days_since_last_sale`, `confidence`.

**Current implementation status:** Level 2 **lite** is selectable in Streamlit `/Discount`.

### Level 3 — Promotion strategy (beyond flat %)

- **Add:** playbooks — bundles, BXGY, tiered discount, free-shipping threshold, time-boxed events — as **templates** attached to drafts or sibling objects (not necessarily one `%` only).
- **Engine:** rule-driven suggestion of **playbook type** + parameters; optimization solvers optional later.

**Current implementation status:** Level 3 is selectable in Streamlit `/Discount` and adds `campaign_type` + `campaign_template` to drafts (`schema_version = 3`).

### Level 4 — Profit-aware optimization

- **Requires:** costs or margin assumptions (per SKU, category, or vertical).
- **Output:** trade-offs (e.g. lower discount + higher AOV) with **contribution-style** framing.
- **Without cost data:** keep margin language as **proxy** only (current retained-value bands).

### Level 5 — Autonomous execution

- **Requires:** execution channel (Shopify APIs), guardrails (max discount, margin floor, SKU allowlist), measurement/feedback loop.
- **Human role:** constraints, monitoring, rollback — not day-to-day % tuning.

---

## 4) Implementation notes for integrators

1. **Do not break** `PromotionDraft.to_dict()` without bumping `schema_version` and documenting migration.
2. Prefer **extending** drafts and placeholder GraphQL over hard-coding Shopify fields inside `discount_recommendation.py`.
3. When connecting Shopify, resolve **variant GIDs** from synced catalog; SKU string alone is not enough for all stores.
4. When moving logic into the main engine, persist or reference **upload_id**, **signal codes**, and **metric snapshots** used for each recommendation row for audit.

---

## 5) File index

| Path | Purpose |
|------|---------|
| `app/services/discount_recommendation.py` | Heuristic SKU recommendations |
| `app/services/promotion_draft.py` | Draft model + `from_discount_rows` |
| `app/integration/shopify_discounts.py` | Flag + placeholder + future `create_*` |
| `app/config.py` | `shopify_discount_integration_enabled` |
| `streamlit_app/pages/8_Discount.py` | UI + JSON download |
