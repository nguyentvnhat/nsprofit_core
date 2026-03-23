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
You are a senior Python backend engineer.

Continue the NosaProfit project in the CURRENT FOLDER based on the architecture already generated.

Your task is to implement the database foundation and SQLAlchemy models for the NosaProfit MVP.

Tech stack:
- Python 3.11+
- SQLAlchemy 2.0 style
- MySQL
- pymysql driver
- Alembic-ready structure
- type hints required

Important:
- Follow the existing architecture in the current folder
- Do NOT redesign the project
- Do NOT collapse files into one file
- Keep code modular and production-minded
- Assume this project will later expand into customers, products, transactions, discounts, refunds, and shipping
- Use MySQL-compatible field types and defaults

---

# GOALS

Implement:

1. database connection layer
2. declarative base
3. timestamp mixin
4. all SQLAlchemy models for MVP
5. model relationships
6. indexes and constraints
7. __init__.py exports for models
8. a simple test_db.py script that validates table creation

---

# REQUIRED FILES TO IMPLEMENT OR UPDATE

app/config.py
app/database.py

app/models/__init__.py
app/models/base.py
app/models/mixins.py
app/models/upload.py
app/models/raw_order.py
app/models/customer.py
app/models/order.py
app/models/order_item.py
app/models/metric_snapshot.py
app/models/signal_event.py
app/models/insight.py
app/models/rule_definition.py

test_db.py

If there is already partial code, improve it instead of replacing architecture.

---

# CONFIG REQUIREMENTS

Implement app/config.py to:
- load environment variables from .env using python-dotenv
- expose NOSAPROFIT_DATABASE_URL safely
- raise a clear error if database URL is missing

Expected env var:
NOSAPROFIT_DATABASE_URL=mysql+pymysql://user:pass@127.0.0.1:3306/nosaprofit

---

# DATABASE REQUIREMENTS

Implement app/database.py with:
- SQLAlchemy engine
- session factory
- declarative base import
- helper to get DB session
- safe MySQL options
- future-friendly SQLAlchemy 2.0 style

---

# BASE / MIXIN REQUIREMENTS

Create:
1. base.py
2. mixins.py

Requirements:
- use DeclarativeBase
- create a TimestampMixin
- created_at and updated_at must be MySQL-safe
- use server defaults compatible with MySQL
- avoid invalid datetime defaults
- use:
  - server_default=text("CURRENT_TIMESTAMP")
  - and updated_at with MySQL-safe update behavior if appropriate
- do NOT use invalid default datetime expressions

---

# MODEL REQUIREMENTS

Implement the following tables:

## 1. uploads
Purpose:
- track uploaded source files and processing status

Fields:
- id
- file_name
- file_type
- source_type
- status
- row_count
- uploaded_at
- processed_at
- error_message
- created_at
- updated_at

Suggested details:
- source_type example: shopify_csv
- status example: uploaded / parsed / normalized / processed / failed

Relationships:
- uploads -> raw_orders
- uploads -> orders
- uploads -> metric_snapshots
- uploads -> signal_events
- uploads -> insights

---

## 2. raw_orders
Purpose:
- store raw source rows for traceability/debugging

Fields:
- id
- upload_id
- row_number
- raw_payload_json
- created_at
- updated_at

Requirements:
- use JSON type if suitable, otherwise MySQL-compatible approach
- indexed by upload_id and row_number

---

## 3. customers
Purpose:
- normalized customer-level entity

Fields:
- id
- email
- name
- first_order_date
- last_order_date
- total_orders
- total_spent
- created_at
- updated_at

Requirements:
- email indexed
- nullable email allowed because Shopify exports may have missing customer fields

Relationships:
- customers -> orders

---

## 4. orders
Purpose:
- normalized order-level record

Fields:
- id
- upload_id
- external_order_id
- order_name
- order_date
- currency
- financial_status
- fulfillment_status
- source_name
- customer_id
- shipping_country
- subtotal_price
- discount_amount
- shipping_amount
- tax_amount
- refunded_amount
- total_price
- net_revenue
- total_quantity
- is_cancelled
- is_repeat_customer
- created_at
- updated_at

Requirements:
- indexes on:
  - upload_id
  - external_order_id
  - order_date
  - source_name
  - customer_id
- choose precise numeric types for money values
- use Integer for quantities / booleans for flags

Relationships:
- orders -> upload
- orders -> customer
- orders -> order_items

---

## 5. order_items
Purpose:
- normalized line-item-level records

Fields:
- id
- order_id
- sku
- product_name
- variant_name
- vendor
- quantity
- unit_price
- line_discount_amount
- line_total
- net_line_revenue
- requires_shipping
- created_at
- updated_at

Requirements:
- indexes on:
  - order_id
  - sku
  - product_name
- money fields use precise numeric type

Relationships:
- order_items -> orders

---

## 6. metric_snapshots
Purpose:
- store computed metrics for dashboard and historical comparison

Fields:
- id
- upload_id
- metric_code
- metric_scope
- dimension_1
- dimension_2
- period_type
- period_value
- metric_value
- created_at
- updated_at

Examples:
- metric_code: total_orders, total_revenue, aov
- metric_scope: overall, product, customer, source
- period_type: all_time, day, week, month

Requirements:
- indexed for dashboard lookup
- metric_value should support decimal numeric values

---

## 7. signal_events
Purpose:
- store detected business signals

Fields:
- id
- upload_id
- signal_code
- severity
- entity_type
- entity_key
- signal_value
- threshold_value
- signal_context_json
- created_at
- updated_at

Requirements:
- signal_context_json stores structured context
- indexes on upload_id, signal_code, severity

---

## 8. insights
Purpose:
- store generated narrative insights

Fields:
- id
- upload_id
- insight_code
- category
- priority
- title
- summary
- implication_text
- recommended_action
- supporting_data_json
- created_at
- updated_at

Requirements:
- indexes on upload_id, category, priority
- title/summary should use suitable text lengths
- implication/recommended_action can be Text

---

## 9. rule_definitions
Purpose:
- optional persistence for rule definitions if later needed

Fields:
- id
- rule_code
- category
- is_active
- severity
- condition_json
- title_template
- summary_template
- implication_template
- action_template
- created_at
- updated_at

Requirements:
- unique rule_code
- JSON/text for condition_json
- this table is future-ready even if YAML rules are primary in MVP

---

# MODELING RULES

1. Use SQLAlchemy 2.0 typed ORM style:
   - Mapped[]
   - mapped_column()
   - relationship()

2. Use Decimal-friendly numeric columns for money:
   - Numeric(18, 2) or similar

3. Use clear nullable settings
4. Use sensible String lengths
5. Add __repr__ only if useful and concise
6. Add back_populates consistently
7. Add cascade behavior where appropriate
8. Add explicit __tablename__

---

# MODELS INIT REQUIREMENT

In app/models/__init__.py export:
- Base
- all model classes

This must allow:

from app.models import Base, Upload, RawOrder, Customer, Order, OrderItem, MetricSnapshot, SignalEvent, Insight, RuleDefinition

---

# TEST SCRIPT REQUIREMENT

Implement test_db.py that:
- imports engine
- imports Base
- imports all models
- runs Base.metadata.create_all(bind=engine)
- prints a clear success message
- catches exceptions and prints readable failure output

---

# OUTPUT FORMAT REQUIREMENTS

Return:
1. each file path
2. the code for that file
3. only files relevant to this task
4. code must be directly usable

---

# IMPORTANT SAFETY / QUALITY NOTES

- Do NOT use invalid MySQL datetime defaults
- Do NOT use SQLite-specific behavior
- Do NOT write pseudo-code
- Do NOT leave TODO placeholders for core fields
- Do NOT move business logic into models
- Keep models clean and focused on persistence

---

# SUCCESS CRITERIA

The generated code must:
- work with MySQL
- avoid the previous created_at default error
- be migration-friendly
- support future expansion
- preserve the project architecture already created


#PROMPT 3

You are a senior Python data engineer.

Continue the NosaProfit project in the CURRENT FOLDER.

Your task is to implement a robust Shopify CSV parser service.

---

# 🎯 GOAL

Build a production-minded CSV parser that:

1. Reads Shopify order export CSV files
2. Handles messy real-world data safely
3. Validates required structure
4. Normalizes column naming inconsistencies
5. Returns structured raw rows for normalization layer
6. Supports large files
7. Is reusable and testable

---

# 📂 TARGET FILE

app/services/file_parser.py

---

# 🧠 CONTEXT

Shopify order export CSV:
- Each row = 1 line item
- Same order appears multiple times
- Many columns (40–100+)
- Column names can vary slightly depending on export
- Some fields may be missing or empty

---

# ⚙️ REQUIREMENTS

## 1. Main function

Implement:

```python
def parse_shopify_csv(file_path: str) -> list[dict]:


#PROMPT 4
You are a senior data engineer.

Continue the NosaProfit project in the CURRENT FOLDER.

Your task is to implement a Shopify normalization service that transforms raw parsed CSV rows into structured entities ready for database insertion.

---

# 🎯 GOAL

Transform raw rows into:

1. orders (order-level)
2. order_items (line-item-level)
3. customers (customer-level)

---

# 📂 TARGET FILE

app/services/shopify_normalizer.py

---

# 🧠 CONTEXT

Input:
- list[dict] from parse_shopify_csv()

Important:
- Each row = 1 line item
- Same order appears multiple times
- Need grouping logic

---

# ⚙️ REQUIREMENTS

## 1. Main function

```python
def normalize_shopify_data(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]: