# PROMP1

You are a senior Python architect designing a production-minded MVP for a data analytics product called NosaProfit.

Context:
NosaProfit analyzes Shopify order export data to generate business insights about revenue quality, pricing, customer behavior, and operational risks.

Tech stack:
- Python 3.11+
- MySQL
- SQLAlchemy ORM
- Pandas
- Streamlit (for MVP frontend)
- YAML for rule configuration

Goal:
Build a clean, modular, extensible project architecture that supports:

1. Upload Shopify CSV
2. Parse and normalize order + line item data
3. Store normalized data into MySQL
4. Compute metrics
5. Detect business signals
6. Apply rules
7. Generate narrative insights
8. Display results in Streamlit dashboard

---

# 🔴 CRITICAL ARCHITECTURAL REQUIREMENTS

1. The system MUST be modular and extensible.
2. DO NOT put business logic inside Streamlit UI.
3. Separate clearly:
   - data models
   - repositories
   - services
   - rules
   - UI layer

4. Design for future expansion beyond orders:
   - customers
   - products
   - transactions
   - discounts
   - refunds
   - shipping

5. Metrics must be modular:
   - each metric or metric group should be extendable
   - do NOT create one giant function

6. Signals must be pluggable:
   - grouped by domain (revenue, product, customer, risk)

7. Rules must be externalized:
   - stored in YAML files
   - NOT hardcoded in Python

8. Insight generation must be separate from rule evaluation:
   - rule → signal → insight payload → narrative layer

9. Architecture must support future migration into:
   - API backend (FastAPI or similar)
   - multi-tenant SaaS

---

# 🧱 REQUIRED PROJECT STRUCTURE

Generate a full directory structure like this:

nosaprofit/
  app/
    main.py
    config.py
    database.py

    models/
      upload.py
      raw_order.py
      order.py
      order_item.py
      customer.py
      metric_snapshot.py
      signal_event.py
      insight.py
      rule_definition.py

    repositories/
      upload_repository.py
      order_repository.py
      metric_repository.py
      signal_repository.py
      insight_repository.py

    services/
      file_parser.py
      shopify_normalizer.py
      metrics_engine/
        __init__.py
        revenue_metrics.py
        order_metrics.py
        product_metrics.py
        customer_metrics.py

      signal_engine/
        __init__.py
        revenue_signals.py
        product_signals.py
        customer_signals.py
        risk_signals.py

      rules_engine.py
      narrative_engine.py
      dashboard_service.py

    rules/
      revenue_rules.yaml
      product_rules.yaml
      customer_rules.yaml
      risk_rules.yaml

    utils/
      dates.py
      money.py
      grouping.py
      validators.py

  streamlit_app/
    Home.py
    pages/
      1_Overview.py
      2_Orders.py
      3_Products.py
      4_Customers.py
      5_Risks.py
      6_Insights.py

  tests/
  migrations/
  requirements.txt
  README.md

---

# 🗄️ DATABASE DESIGN REQUIREMENTS

Define SQLAlchemy models for:

- uploads
- raw_orders
- customers
- orders
- order_items
- metric_snapshots
- signal_events
- insights
- rule_definitions

Requirements:
- MySQL-compatible types
- timestamps (created_at, updated_at)
- proper indexing
- foreign keys and relationships
- nullable vs required fields handled correctly

---

# ⚙️ SERVICES REQUIREMENTS

## file_parser.py
- Read Shopify CSV
- Validate structure
- Return structured raw rows

## shopify_normalizer.py
- Transform raw rows into:
  - order-level records
  - order-item-level records
- Compute:
  - subtotal
  - discounts
  - shipping
  - tax
  - refunds
  - total_price
  - net_revenue
  - total_quantity
- Extract customer + source info

## metrics_engine/
- Modular metrics calculators
- Support:
  - overall metrics
  - time-based metrics
  - product metrics
  - customer metrics
- Return structured results

## signal_engine/
- Detect patterns:
  - revenue vs AOV
  - discount dependency
  - product concentration
  - repeat vs new customer value
  - refund issues
  - free shipping overuse
- Configurable thresholds
- Return signal objects

## rules_engine.py
- Load YAML rules
- Evaluate conditions against metrics/signals
- Support operators:
  - >, >=, <, <=, ==, compare-to-metric
- Output structured insight payloads

## narrative_engine.py
- Convert rule outputs into:
  - title
  - summary
  - implication
  - action
- Must be deterministic (NO LLM calls)

## dashboard_service.py
- Aggregate data for UI
- Provide ready-to-use data for Streamlit

---

# 📊 STREAMLIT REQUIREMENTS

- Upload Shopify CSV
- Trigger processing pipeline
- Display:
  - KPI cards
  - charts
  - tables
  - insight cards
- Pages:
  - Overview
  - Orders
  - Products
  - Customers
  - Risks
  - Insights

IMPORTANT:
- Streamlit must NOT contain business logic
- Only call service layer

---

# 🧠 DESIGN PRINCIPLES

- Clean architecture
- Separation of concerns
- Extensibility over shortcuts
- MVP-ready but scalable
- Easy to plug in:
  - new metrics
  - new signals
  - new rules
  - new data sources

---

# 📦 OUTPUT REQUIREMENTS

1. Full folder structure
2. File-by-file explanation
3. Starter code for:
   - database connection
   - models
   - parser
   - normalizer
   - one example metric
   - one example signal
   - one example rule
   - one example insight output
4. Clean, production-minded code style
5. Type hints included

---

# 🚫 DO NOT

- Do NOT put everything in one file
- Do NOT hardcode business rules in UI
- Do NOT tightly couple parsing and metrics
- Do NOT skip normalization layer

---

# ✅ SUCCESS CRITERIA

The output must:
- Be runnable as a base project
- Be clean and readable
- Be extendable without major refactor
- Support future SaaS direction


#PROMPT 2
