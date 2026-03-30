# NosaProfit Decision Flow (metrics → signals → rules → insights → decision formatter)

This document summarizes the current production flow so future upgrades stay compatible.

---

## 1) End-to-end pipeline overview

The system runs in this order:

1. `metrics_engine`  
2. `signal_engine`  
3. `rules_engine`  
4. `narrative_engine` (insight text)  
5. `dashboard_service` + campaign enrichment + UI/PDF decision formatting

Core orchestration paths:

- Store-level ingestion path: `app/services/pipeline.py`
- Campaign-level slicing path: `app/services/campaign_analyzer.py`
- Dashboard assembly path: `app/services/dashboard_service.py`

**SKU discount recommendations & promotion drafts** (parallel path today, not rule-engine fed): see [discount-recommendation.md](discount-recommendation.md).

---

## 2) Stage-by-stage mapping (current modules)

### A. Metrics

- Entry: `run_all_metrics()` in `app/services/metrics_engine/__init__.py`
- Outputs grouped domain metrics (`revenue`, `orders`, `products`, `customers`, `advanced`)
- Flatten helper: `metrics_as_flat_dict()`

Used by:

- `pipeline.py` (store-level)
- `campaign_analyzer.py` (per-campaign buckets)

### B. Signals

- Entry: `run_all_signals()` in `app/services/signal_engine/__init__.py`
- Signal shape includes:
  - `signal_code`
  - `severity`
  - `signal_value` (observed)
  - `threshold_value` (rule threshold)
  - `context`

### C. Rules

- Entry: `evaluate_rules()` in `app/services/rules_engine.py`
- Inputs:
  - flattened metric map
  - active signal codes (`signal_codes(...)`)
- Output: rule insight payloads with matched rule context

### D. Insights / Narration

- Entry: `narrate_all()` in `app/services/narrative_engine.py`
- Converts rule payloads into human-facing insight objects:
  - `title`
  - `summary`
  - `implication`
  - `action`
  - `priority/category` from rule + narrative layer

### E. Decision formatter layer (current)

There is no single `decision_formatter.py` yet. The role is distributed:

- `dashboard_service.py`
  - builds page payload (`DashboardData`)
  - computes top-level decision blocks (`quick_wins`, `loss_drivers`, etc.)
- `campaign_insight_enricher.py`
  - adds impact proxies:
    - `estimated_loss`
    - `opportunity_size`
    - `priority_score`
    - `why_now`
    - `estimated_impact_text`
- `streamlit_app/pages/7_Campaigns.py`
  - UI presentation decisions (top opportunities, actions, collapse levels)
- `streamlit_app/pages/8_Discount.py`
  - Per-SKU discount suggestions + JSON promotion drafts ([discount-recommendation.md](discount-recommendation.md))
- `streamlit_app/campaigns_report_pdf.py`
  - PDF-oriented decision presentation
- `app/services/pdf_export_service.py`
  - HTML/CSS executive report export with WeasyPrint

---

## 3) Data contracts to keep stable

### Signal event contract (important)

`signal_events` equivalent objects are expected to preserve:

- `signal_code`
- `severity`
- `signal_value`
- `threshold_value`
- `entity_type` / `entity_key`
- `context`

Why it matters:

- UI and PDF explain *why* a signal fired via `signal_value` vs `threshold_value`.

### Campaign enriched insight contract

`enriched_campaign_insights` rows are expected to include:

- `campaign`
- `title`
- `priority`
- `category`
- `signal_code`
- `revenue`
- `net_revenue`
- `orders`
- `aov`
- `discount_rate`
- `impacted_revenue`
- `estimated_loss`
- `opportunity_size`
- `priority_score`
- `rank`
- `why_now`
- `estimated_impact_text`
- `summary`
- `implication`
- `action`

---

## 4) Upgrade-safe extension points

Use these points for future upgrades without breaking analytics logic:

1. **New computed display fields**
   - Add in `campaign_insight_enricher.py` (not Streamlit)
2. **New dashboard sections**
   - Add in `dashboard_service.py` as derived payload fields
3. **Rendering changes only**
   - Update Streamlit pages / report templates only
4. **New export formats**
   - Add service under `app/services/*_export_service.py` using existing `DashboardData`

Avoid:

- Recomputing metrics/signals/rules inside UI/export layers
- Duplicating enrichment formulas in Streamlit
- Mixing rule logic into templates

---

## 5) Recommended future refactor (optional)

If you want a true single decision formatter module:

- Create `app/services/decision_formatter.py`
- Move cross-channel (UI + PDF) formatting helpers there:
  - impact basis labels
  - action sentence builders
  - priority badges text
- Keep it pure and deterministic (no DB, no Streamlit import)

This can reduce drift between `/Campaigns` UI and PDF wording.

---

## 6) Quick trace for debugging

When a value in `/Campaigns` looks wrong, trace in this order:

1. `campaign_analyzer.py` output (`campaign_results`)
2. `campaign_insight_enricher.py` enriched row
3. `dashboard_service.py` assignment to `DashboardData`
4. Streamlit page render (`7_Campaigns.py`)
5. PDF render path (`campaigns_report_pdf.py` or `pdf_export_service.py`)

This is the fastest way to isolate whether the issue is:

- analytics logic,
- enrichment logic,
- or presentation-only.

---

## 7) Prompt-ready package for ChatGPT upgrades

Use this section when you want ChatGPT to propose new `metrics / signals / rules / insights` safely.

### A. What to provide as input context

Before asking for upgrades, give ChatGPT:

1. **Business context**
   - Industry (fashion, beauty, electronics, grocery, subscription, etc.)
   - Revenue model (one-time, repeat, subscription)
   - Main channels (Meta, Google, TikTok, CRM, affiliates, organic)
2. **Data availability**
   - Confirm which fields exist and are reliable (`revenue`, `net_revenue`, `orders`, `aov`, `discount_rate`, `refunds`, `repeat_rate`, etc.)
   - Identify missing fields (so suggestions can use proxy logic)
3. **Current contracts from this doc**
   - Signal event contract
   - Enriched campaign insight contract
4. **Current pain points**
   - Example: "too many generic actions", "many zero-dollar impacts", "signal wording hard for non-technical users"
5. **Success criteria**
   - Example: "all insights must have concrete money/action language"
   - Example: "output must be deterministic and backward compatible"

### B. Upgrade constraints to include in prompt

Ask ChatGPT to respect these constraints:

- Keep existing contracts backward compatible.
- Prefer deterministic formulas (no random/statistical black-box in UI layer).
- Put business logic in engines/enricher, not in templates/UI.
- Separate **Measured** vs **Estimated (proxy)** explicitly.
- For every new rule, include threshold rationale and edge-case behavior.
- For every new action, prefer money-driven text (`save $X` / `gain $Y`).

### C. Required output format from ChatGPT

Tell ChatGPT to return upgrades in this structure:

1. **New metric definitions**
   - name, formula, required columns, fallback behavior
2. **New signal definitions**
   - signal_code, trigger condition, severity mapping, context fields
3. **Rule additions/changes**
   - YAML-like condition, priority, narrative intent
4. **Insight templates**
   - title, summary, implication, action, why_now style
5. **Money logic**
   - measured formula and proxy formula (with assumptions)
6. **Implementation map**
   - exact file targets in this repo
7. **Test checklist**
   - unit cases and expected outputs

### D. Copy-paste prompt template

```text
You are upgrading an ecommerce analytics pipeline in Python.

Pipeline order:
1) metrics_engine
2) signal_engine
3) rules_engine
4) narrative_engine
5) dashboard_service + campaign_insight_enricher + UI/PDF formatters

Non-negotiable contracts:
- Signal event fields: signal_code, severity, signal_value, threshold_value, entity_type/entity_key, context
- Enriched campaign insight fields: campaign, title, priority, category, signal_code, revenue, net_revenue, orders, aov, discount_rate, impacted_revenue, estimated_loss, opportunity_size, priority_score, rank, why_now, estimated_impact_text, summary, implication, action

Business context:
- Industry: <fill>
- Revenue model: <fill>
- Channels: <fill>
- Known reliable fields: <fill>
- Missing fields: <fill>
- Current pain points: <fill>

Your tasks:
1) Propose new metrics, signals, and rules for this context.
2) Keep backward compatibility with existing contracts.
3) Separate measured vs estimated(proxy) money basis.
4) Provide money-driven actions with deterministic formulas.
5) Avoid UI/template logic; place logic in engine/enricher layers.

Output exactly in sections:
A) Metrics
B) Signals
C) Rules
D) Insight copy templates
E) Money formulas (Measured + Proxy + assumptions)
F) File-by-file implementation plan
G) Test cases (input -> expected)
H) Risks / rollback plan
```

---

## 8) Industry-specific examples (starter ideas)

Use these as references when asking for upgrades. Keep names deterministic and business-readable.

### A. Fashion / Apparel

- **Metric ideas**
  - `promo_dependency_rate` = discounted_orders / total_orders
  - `size_return_rate` = returns_due_to_size / total_orders
- **Signal ideas**
  - `PROMO_DEPENDENCY_HIGH` when `promo_dependency_rate > 0.55`
  - `SIZE_FIT_RETURN_SPIKE` when `size_return_rate` exceeds baseline by threshold
- **Rule/insight angle**
  - Margin erosion from over-promotion
  - Fit/size guide optimization to reduce returns

### B. Beauty / Personal Care

- **Metric ideas**
  - `repeat_60d_rate` = repeat_customers_60d / customers
  - `bundle_attach_rate` = orders_with_bundle / total_orders
- **Signal ideas**
  - `LOW_REPEAT_60D`
  - `BUNDLE_ATTACH_LOW`
- **Rule/insight angle**
  - Subscription/replenishment nudges
  - Routine bundle strategy to lift AOV and retention

### C. Electronics / Gadgets

- **Metric ideas**
  - `accessory_attach_rate` = accessory_orders / core_device_orders
  - `warranty_attach_rate` = warranty_orders / eligible_orders
- **Signal ideas**
  - `ACCESSORY_ATTACH_GAP`
  - `WARRANTY_ATTACH_LOW`
- **Rule/insight angle**
  - Opportunity-focused upsell with clear incremental revenue estimate

### D. Grocery / FMCG

- **Metric ideas**
  - `basket_depth` = items_per_order
  - `stockout_proxy_rate` from canceled_or_substituted_items / ordered_items
- **Signal ideas**
  - `BASKET_DEPTH_DECLINE`
  - `STOCKOUT_RISK_HIGH`
- **Rule/insight angle**
  - Protect repeat behavior by reducing stockout-driven churn

### E. Subscription businesses

- **Metric ideas**
  - `involuntary_churn_rate` = failed_renewals / scheduled_renewals
  - `dunning_recovery_rate` = recovered_failed_payments / failed_payments
- **Signal ideas**
  - `INVOLUNTARY_CHURN_HIGH`
  - `DUNNING_RECOVERY_LOW`
- **Rule/insight angle**
  - Revenue-at-risk protection with payment retry optimization

### Money basis examples by signal type

- **Measured** (direct): refunds, chargebacks, known discount amount.
- **Estimated (proxy)**: concentration risk, low repeat risk, unstable growth risk, attach-rate opportunity.

For proxy signals, always include:

1. base amount (usually impacted revenue),
2. proxy coefficient (deterministic percent),
3. reason for coefficient choice,
4. confidence note (low/medium/high).

