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


#PROMPT 5
You are a senior data engineer.

Continue the NosaProfit project in the CURRENT FOLDER.

Your task is to implement the metrics engine for NosaProfit.

---

# 🎯 GOAL

Compute business metrics from normalized data:

Input:
- orders
- order_items
- customers

Output:
- structured metrics dict
- ready for:
  - signal engine
  - dashboard
  - database storage

---

# 📂 TARGET FOLDER

app/services/metrics_engine/

---

# 📁 REQUIRED FILES

metrics_engine/
  __init__.py
  revenue_metrics.py
  order_metrics.py
  product_metrics.py
  customer_metrics.py

---

# 🧠 DESIGN REQUIREMENTS

1. Modular architecture
- Each file = 1 domain
- Do NOT create one giant function

2. Pure functions
- No DB access here
- No side effects

3. Output must be structured

4. Use Decimal-safe calculations

5. Easy to extend later

---

# ⚙️ CORE METRICS TO IMPLEMENT

## 1. Revenue metrics (revenue_metrics.py)

Implement:

- total_orders
- gross_revenue (sum of total_price)
- net_revenue (sum of net_revenue)
- total_discounts
- total_refunds
- total_shipping
- total_tax
- AOV = net_revenue / total_orders
- median_order_value

---

## 2. Order quality metrics (order_metrics.py)

Implement:

- total_units_sold
- average_units_per_order
- discounted_order_rate
- refunded_order_rate
- free_shipping_rate
- low_value_order_rate (< threshold)
- high_value_order_rate (> threshold)

Thresholds configurable

---

## 3. Product metrics (product_metrics.py)

Implement:

- product_revenue (by SKU)
- product_units
- top_3_sku_share (% revenue)
- product_discount_rate
- product_refund_rate (if possible)

---

## 4. Customer metrics (customer_metrics.py)

Implement:

- total_customers
- new_customer_count
- repeat_customer_count
- repeat_customer_rate
- new_customer_AOV
- repeat_customer_AOV
- top_customer_revenue_share

---

# 🧠 DATA HANDLING RULES

- Always handle division by zero
- Always use Decimal-safe math
- Ignore None safely
- Skip invalid rows instead of crashing

---

# 📦 OUTPUT FORMAT

Return ONE structured dict:

```python
{
  "revenue": {...},
  "orders": {...},
  "products": {...},
  "customers": {...}
}

#PROMPT 6 not
You are a senior data engineer and business analytics expert.

Continue the NosaProfit project in the CURRENT FOLDER.

Your task is to implement the Signal Engine for NosaProfit.

---

# 🎯 GOAL

Convert computed metrics into structured business signals.

Input:
- metrics dict (from metrics engine)

Output:
- list of signal objects

Each signal represents:
- a detected pattern
- a risk
- an opportunity
- or an anomaly

---

# 📂 TARGET FOLDER

app/services/signal_engine/

---

# 📁 REQUIRED FILES

signal_engine/
  __init__.py
  revenue_signals.py
  product_signals.py
  customer_signals.py
  risk_signals.py

---

# 🧠 DESIGN REQUIREMENTS

1. Modular design
- each file = 1 domain
- no giant function

2. Pure functions
- no DB access
- no side effects

3. Configurable thresholds
- defined at top of file or config dict

4. Return structured signal objects

---

# 📦 SIGNAL OBJECT FORMAT

Each signal must look like:

```python
{
  "signal_code": "high_discount_dependency",
  "category": "pricing",
  "severity": "high",   # low / medium / high
  "entity_type": "overall",  # or product / customer / source
  "entity_key": None,
  "signal_value": 18.5,
  "threshold_value": 15,
  "context": {
    "discount_rate": 18.5,
    "total_orders": 1200
  }
}

#PROMPT 7 - NOT
You are a senior analytics engineer and business strategist.

Continue the NosaProfit project in the CURRENT FOLDER.

Your task is to implement:

1. Rules Engine
2. Narrative Engine

These components convert signals into business insights.

---

# 🎯 GOAL

Input:
- metrics dict
- signals list

Output:
- list of structured insights ready for UI

---

# 📂 TARGET FILES

app/services/rules_engine.py
app/services/narrative_engine.py

app/rules/
  revenue_rules.yaml
  product_rules.yaml
  customer_rules.yaml
  risk_rules.yaml

---

# 🧠 DESIGN REQUIREMENTS

1. Rules must be DATA-DRIVEN (YAML)
2. No hardcoded business logic in Python
3. Rules must be easy to extend
4. Narrative must be deterministic (NO LLM)
5. Separation:
   - rules_engine → logic
   - narrative_engine → text generation

---

# 📦 RULE STRUCTURE (YAML)

Each rule must define:

- rule_code
- category
- severity
- condition
- title_template
- summary_template
- implication_template
- action_template

---

# 🧪 CONDITION FORMAT

Support:

- metric comparison
- signal existence
- metric vs metric

Example:

```yaml
condition:
  all:
    - type: metric
      metric: discount_rate
      operator: ">"
      value: 15

    - type: signal
      signal_code: high_discount_dependency


#prompt 8 - not
You are a senior frontend + data application engineer.

Continue the NosaProfit project in the CURRENT FOLDER.

Your task is to build a Streamlit dashboard UI for NosaProfit.

---

# 🎯 GOAL

Build a clean, modular Streamlit app that:

1. Allows user to upload Shopify CSV
2. Runs full pipeline:
   - parser
   - normalizer
   - metrics
   - signals
   - insights
3. Displays:
   - KPIs
   - charts
   - tables
   - insight cards

---

# 📂 TARGET FOLDER

streamlit_app/

---

# 📁 REQUIRED FILES

streamlit_app/
  Home.py
  pages/
    1_Overview.py
    2_Orders.py
    3_Products.py
    4_Customers.py
    5_Risks.py
    6_Insights.py

---

# 🧠 DESIGN RULES

1. NO BUSINESS LOGIC IN UI
- UI only calls service layer

2. Use a shared service:

app/services/dashboard_service.py

This service should:
- orchestrate pipeline
- return ready-to-use data

---

# ⚙️ PIPELINE FLOW

When file uploaded:

1. parse_shopify_csv()
2. normalize_shopify_data()
3. compute_metrics()
4. generate_signals()
5. evaluate_rules()
6. generate_insights()

---

# 🎨 UI REQUIREMENTS

## Home.py

- title: "NosaProfit"
- upload CSV
- trigger pipeline
- store results in session state

---

## 1_Overview.py

Display:

- KPI cards:
  - total revenue
  - net revenue
  - AOV
  - total orders
- simple charts:
  - revenue over time
  - order count over time

---

## 2_Orders.py

- table of orders
- filters:
  - date
  - country
  - status

---

## 3_Products.py

- top products table
- revenue by SKU
- top 3 SKU share

---

## 4_Customers.py

- new vs repeat
- AOV comparison
- top customers

---

## 5_Risks.py

- show signals grouped by severity:
  - high
  - medium
  - low

---

## 6_Insights.py

- show insights as cards:

Each card:
- title
- summary
- implication
- action
- priority badge

---

# ⚙️ IMPLEMENTATION DETAILS

- use st.session_state to store processed data
- use pandas DataFrame for tables
- use st.metric for KPI
- use st.bar_chart / st.line_chart
- use st.expander for details
- clean layout

---

# 🧠 UX RULES

- fast load
- no clutter
- focus on decision-making
- highlight insights clearly

---

# 🧪 ERROR HANDLING

- if no file → show message
- if processing fails → show error
- prevent crash

---

# 🚫 DO NOT

- Do NOT compute metrics in UI
- Do NOT parse CSV in UI directly
- Do NOT duplicate logic

---

# ✅ SUCCESS CRITERIA

The app must:

- run end-to-end
- allow file upload
- show meaningful KPIs
- show insights clearly
- be clean and usable

---

# 📦 OUTPUT

Return:
1. all Streamlit files
2. dashboard_service.py (if not exists)
3. clean, production-ready code



#Propmt #9 - Advances metrics
You are a senior data engineer building a Shopify revenue analytics engine.

Extend the existing metrics engine to compute ADVANCED METRICS required for business insights.

Input:
- orders
- line_items
- customers

Output:
Return a dictionary with these additional metrics:

1. monthly_revenue: dict[month → revenue]
2. monthly_orders: dict[month → order count]
3. monthly_aov: dict[month → AOV]

4. top_sku_revenue_share:
   - revenue of top SKU / total revenue

5. sku_revenue_distribution:
   - dict[sku → revenue]

6. order_value_distribution:
   - buckets:
     <25, 25–50, 50–100, 100–200, >200

7. low_value_order_ratio:
   - % orders < 50

8. discount_amount_total
9. discount_rate:
   - total discount / gross revenue

10. compare_at_discount_total:
   - sum(compare_at_price - price)

11. bundle_pairs:
   - top 10 product pairs bought together
   - format: [(sku1, sku2, count)]

12. source_revenue_distribution:
   - dict[source → revenue]

13. top_source_share:
   - highest source revenue %

14. blank_sku_revenue:
   - revenue from line items with empty SKU

15. orders_near_free_shipping_threshold:
   - % orders within 10% below threshold (assume threshold = 60)

16. revenue_growth:
   - last month vs previous

17. aov_growth:
   - last month vs previous

Requirements:
- clean Python
- no external API
- handle missing data safely
- modular functions


#############################################################
#Prompt 10 - signal engine improvements
You are a revenue intelligence system.

Using the advanced metrics, generate SIGNALS (structured patterns, not insights yet).

Input:
- metrics dict

Output:
Return a dict of boolean or numeric signals:

Signals to implement:

1. high_discount_dependency:
   discount_rate > 0.2

2. stacked_discounting:
   compare_at_discount_total > 0 AND discount_amount_total > 0

3. volume_driven_growth:
   revenue_growth > 0 AND aov_growth <= 0

4. hero_sku_concentration:
   top_sku_revenue_share > 0.4

5. low_order_value_problem:
   low_value_order_ratio > 0.5

6. free_shipping_opportunity:
   orders_near_free_shipping_threshold > 0.3

7. source_concentration_risk:
   top_source_share > 0.7

8. bundle_opportunity:
   at least one pair count > threshold

9. data_hygiene_issue:
   blank_sku_revenue > 0

10. unstable_growth:
   revenue fluctuates significantly month-to-month

Requirements:
- return structured signals
- do NOT generate human text
- pure logic only

#prompt 11 rule engine - not 
You are a Shopify revenue strategist.

Convert signals into BUSINESS RULE FLAGS.

Input:
- signals dict

Output:
Return list of triggered rules:

Rules:

- if high_discount_dependency:
  "discount_dependency_risk"

- if stacked_discounting:
  "double_discounting_issue"

- if volume_driven_growth:
  "low_quality_growth"

- if hero_sku_concentration:
  "sku_concentration_risk"

- if low_order_value_problem:
  "aov_structure_issue"

- if free_shipping_opportunity:
  "free_shipping_optimization_opportunity"

- if source_concentration_risk:
  "channel_dependency_risk"

- if bundle_opportunity:
  "bundle_revenue_opportunity"

- if data_hygiene_issue:
  "data_quality_issue"

- if unstable_growth:
  "revenue_instability"

Requirements:
- deterministic mapping
- no explanation

#prompt 12 - insight engine - not

You are a Head of Revenue analyzing a Shopify store.

Generate BUSINESS INSIGHTS from rules.

Input:
- rules list
- metrics

Output:
Return list of insights:

Each insight must include:

- title
- summary (clear, non-technical)
- implication (why it matters)
- action (what to do)
- priority (high/medium/low)

Tone:
- operator mindset
- concise
- actionable
- no fluff

Examples:

discount_dependency_risk:
Title: Discount becoming default sales mechanism

low_quality_growth:
Title: Revenue growth driven by volume, not value

sku_concentration_risk:
Title: Over-reliance on a single product

aov_structure_issue:
Title: Order value structure is limiting growth

free_shipping_optimization_opportunity:
Title: Missed opportunity to increase AOV via shipping threshold

Requirements:
- max 10 insights
- prioritize highest impact
- avoid generic statements
 

###################################
#Prompt 13
You are a senior Streamlit product engineer.

Continue the current NosaProfit project using the EXISTING CODEBASE.

IMPORTANT:
- Reuse the existing DashboardData returned by get_dashboard_data()
- Do NOT change architecture
- Do NOT add business logic in Streamlit
- Keep code directly runnable
- Use existing session handling with active_upload_id and dashboard_data cache

FILE TO MODIFY:
streamlit_app/pages/1_Overview.py

GOAL:
Turn the current Overview page from a basic KPI + chart page into an executive summary page for a Shopify revenue intelligence product.

REQUIREMENTS:
1. Keep the current KPI row:
   - total_revenue
   - net_revenue
   - aov
   - total_orders

2. Keep the current revenue and order trend charts.

3. Remove the "Recent orders" table from the main focus area and place it at the bottom inside an expander called "Recent orders preview".

4. Add a new section: "Top insights"
   - Show up to 3 insights from dashboard.insights
   - Render each as a card with:
     - title
     - priority badge
     - summary
     - implication
     - action

5. Add a new section: "Top risks"
   - Read dashboard.signals_by_severity
   - Show 3 summary metrics:
     - High risks
     - Medium risks
     - Low risks
   - Under that, show up to 2 high-severity items as compact cards with:
     - signal_code
     - signal_value
     - threshold_value
     - entity_type
     - entity_key

6. Add a new section: "Recommended actions"
   - Extract the action field from the first 3 insights that have actions
   - Show them as a numbered action list

7. Handle empty insights and empty risks gracefully.

8. Keep the page executive-friendly, concise, and product-like rather than debug-like.


###################################
 #Prompt 14 
 You are a senior Streamlit product engineer.

Continue the current NosaProfit project using the EXISTING CODEBASE.

IMPORTANT:
- Reuse existing dashboard_service.py and DashboardData
- Do NOT add business logic
- Keep code directly runnable

FILE TO MODIFY:
streamlit_app/pages/5_Risks.py

GOAL:
Upgrade the Risks page from a raw dataframe view into a business-friendly risk dashboard.

REQUIREMENTS:
1. Keep the page title "Risks".

2. At the top, render 3 KPI metrics:
   - High severity count
   - Medium severity count
   - Low severity count

3. For each severity group (high, medium, low):
   - Show a section header
   - If empty, show a simple info message
   - Otherwise render each signal as a bordered card, not only a dataframe

4. Each risk card must show:
   - signal_code
   - observed value (signal_value)
   - threshold value
   - entity type / entity key if available
   - context JSON inside an expander if present

5. Also keep a raw dataframe version inside an expander named:
   - "Show raw table"

6. Use severity-specific visual cues:
   - high = error/warning style
   - medium = warning/info style
   - low = neutral/success style

7. Keep the page readable for non-technical business users.


######################################################
#Prompt 15
You are a senior Streamlit product engineer.

Continue the current NosaProfit project using the EXISTING CODEBASE.

IMPORTANT:
- Reuse existing DashboardData from get_dashboard_data()
- Do NOT add business logic into Streamlit
- Keep code directly runnable

FILE TO MODIFY:
streamlit_app/pages/3_Products.py

GOAL:
Upgrade the Products page so it feels like a revenue intelligence view, not only a product table.

REQUIREMENTS:
1. Keep the existing "Top products" table.
2. Keep the existing "Top 3 SKU share" metric.
3. Keep the existing "Revenue by SKU" bar chart.

4. Add a new "Product concentration" section:
   - show a short interpretation based on dashboard.top_3_sku_share
   - example:
     - if very high, warn about concentration risk
     - if moderate, mention balanced mix
   - keep this lightweight and derived only from existing values

5. Add a new "Top product notes" section:
   - show top 5 products from dashboard.products_table
   - render compact cards or rows with main product fields

6. If dashboard.products_table contains missing or blank SKU-like values, show a warning message.

7. Put the raw table into the main area, but make the right side feel like a decision-support sidebar.

8. Keep the page polished and business-friendly.

#####################################
#Prompt 16
You are a senior Streamlit product engineer.

Continue the current NosaProfit project using the EXISTING CODEBASE.

IMPORTANT:
- Reuse existing DashboardData and insights payload
- Do NOT add business logic
- Keep code directly runnable

FILE TO MODIFY:
streamlit_app/pages/6_Insights.py

GOAL:
Improve the Insights page so priorities are clearer and more executive-friendly.

REQUIREMENTS:
1. Group insights into sections:
   - High Priority
   - Medium Priority
   - Low Priority

2. Treat both "normal" and "medium" as Medium for display.

3. Each insight card must show:
   - title
   - priority badge
   - category
   - summary
   - implication
   - action

4. Within each section, keep existing bordered card style.

5. Add a compact summary row at the top:
   - total insights
   - high priority count
   - medium priority count
   - low priority count

6. Handle empty groups gracefully.

7. Keep the page concise and polished.