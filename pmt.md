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


######################################################
#Prompt 17 
You are a senior Python data engineer and product architect.

Continue the CURRENT NosaProfit codebase in the current folder.

IMPORTANT:
- Reuse the existing architecture
- Do NOT redesign the project
- Do NOT break the current pipeline
- Do NOT move business logic into Streamlit
- Do NOT modify existing metrics/signal/rules/insight logic unless absolutely necessary
- Treat campaign analysis as an additional dimension layer on top of the current system

CURRENT PIPELINE:
orders -> metrics -> signals -> rules -> insights

GOAL:
Add a "Campaign Dimension Layer" so the existing pipeline can run per campaign, without breaking the overall store-level analysis.

==================================================
OBJECTIVE
==================================================

Implement campaign-based analysis for NosaProfit so we can answer:

- Which campaign is driving revenue?
- Which campaign is too dependent on discounts?
- Which campaign has weak order quality?
- Which campaign should be scaled, optimized, or stopped?

The implementation must support:

1. campaign extraction from normalized order data
2. grouping orders by campaign
3. running the existing analysis pipeline per campaign
4. returning structured campaign-level results
5. preparing campaign-level summary data for Streamlit/dashboard usage

==================================================
ARCHITECTURAL RULES
==================================================

1. DO NOT rewrite the current engines.
2. DO NOT hardcode campaign-specific business rules inside metrics_engine, signal_engine, or rules_engine.
3. Campaign must be treated as a dimension, not as a special-case logic branch.
4. Add a thin orchestration layer only.
5. Keep code modular, typed, production-minded, and easy to extend.
6. Preserve existing overall analysis behavior.

==================================================
FILES TO ADD OR UPDATE
==================================================

Create or update only these files if needed:

app/services/campaign_extractor.py
app/services/campaign_analyzer.py
app/services/dashboard_service.py

If needed, you may also make minimal safe updates to:
app/services/shopify_normalizer.py

Do not touch Streamlit pages yet unless required for compatibility.

==================================================
1. CAMPAIGN EXTRACTION
==================================================

Create:
app/services/campaign_extractor.py

Implement a reusable campaign extraction layer.

Expected function(s):

def extract_campaign_key(order: dict) -> str:
    ...

def group_orders_by_campaign(orders: list[dict]) -> dict[str, list[dict]]:
    ...

Requirements:

- Extract campaign from available normalized order fields
- Use a fallback priority chain
- Return a normalized campaign key string
- Never crash on missing fields
- Unknown/empty values should map to "unknown"

Recommended fallback priority:
1. utm_campaign
2. landing_site
3. referrer
4. source_name
5. discount_code
6. "unknown"

Also:
- normalize whitespace
- lowercase campaign keys
- trim overly long raw values if needed
- keep implementation deterministic

==================================================
2. CAMPAIGN ANALYZER
==================================================

Create:
app/services/campaign_analyzer.py

Implement orchestration that runs the existing analysis pipeline per campaign.

Expected function:

def analyze_campaigns(
    orders: list[dict],
    order_items: list[dict],
    customers: list[dict],
) -> list[dict]:
    ...

Requirements:

- Group orders by campaign
- Map related order_items to each campaign using order_id / external_order_id
- Map related customers if possible
- For each campaign:
    - compute metrics using existing metrics engine
    - generate signals using existing signal engine
    - evaluate rules using existing rules engine
    - generate insights using existing narrative/insight layer
- Return structured campaign-level results

Each campaign result should look like:

{
  "campaign": "facebook_ads",
  "order_count": 120,
  "metrics": {...},
  "signals": [...],
  "insights": [...],
  "summary": {
    "revenue": 12345.67,
    "net_revenue": 10222.10,
    "discount_rate": 0.18,
    "aov": 85.20,
    "risk_level": "high"
  }
}

Risk level suggestion:
- high if any high severity signals exist
- medium if any medium severity signals exist
- low otherwise

Do not hardcode too much domain logic.
Keep it lightweight and derived from existing results.

==================================================
3. DASHBOARD SERVICE INTEGRATION
==================================================

Update:
app/services/dashboard_service.py

Goal:
Expose campaign analysis results in the dashboard service output without breaking existing behavior.

Requirements:

- Keep the current dashboard data structure working
- Add campaign-related fields in a backward-compatible way
- If no campaign data can be derived, return empty/default values gracefully

Suggested additional output fields:

campaign_results: list[dict]
campaign_summary_table: list[dict]
top_campaign_risks: list[dict]
top_campaign_insights: list[dict]

campaign_summary_table row format:

[
  {
    "campaign": "facebook_ads",
    "orders": 120,
    "revenue": 12345.67,
    "net_revenue": 10222.10,
    "discount_rate": 0.18,
    "aov": 85.20,
    "risk_level": "high"
  }
]

top_campaign_risks:
- flatten top high-severity campaign signals
- include campaign name in each row

top_campaign_insights:
- flatten top campaign insights
- include campaign name in each row

==================================================
4. DATA COMPATIBILITY
==================================================

The code must work with the current normalized data shape as much as possible.

If normalized orders currently do not contain campaign-friendly fields, make only minimal safe additions in shopify_normalizer.py to preserve fields such as:

- utm_campaign
- landing_site
- referrer
- source_name
- discount_code

Do not refactor the whole normalizer.

==================================================
5. SAFETY / QUALITY RULES
==================================================

- Use type hints
- Keep functions small
- Add concise docstrings
- Handle missing keys safely
- Avoid side effects
- Avoid DB writes in this layer
- No TODO placeholders
- No pseudo-code
- Code must be directly runnable

==================================================
6. OUTPUT FORMAT
==================================================

Return:
1. each file path changed
2. full code for each changed file
3. brief explanation per file
4. preserve existing imports and style where possible

==================================================
SUCCESS CRITERIA
==================================================

The implementation is successful if:

- overall store-level pipeline still works
- campaign-level analysis runs without breaking existing logic
- campaign summary table can be rendered in Streamlit later
- high-risk / high-discount campaigns are visible from structured output
- architecture remains clean and extensible


######################################################
#Prompt 18
You are a senior revenue analytics engineer and product architect.

Continue the CURRENT NosaProfit codebase in the current folder.

IMPORTANT:
- Reuse the existing architecture
- Do NOT redesign the project
- Do NOT break the current store-level pipeline
- Do NOT move business logic into Streamlit UI
- Do NOT rewrite the current metrics, signals, rules, or narrative engines unless absolutely necessary
- Implement a post-processing enrichment layer for campaign insights
- Keep code directly runnable and production-minded

CURRENT STATE:
The /Campaigns page already shows:
- campaign_summary_table
- high-severity signals by campaign
- top_campaign_insights

However, top_campaign_insights are still too qualitative.
They need quantified business impact and ranking so the page becomes more decision-oriented and executive-friendly.

==================================================
GOAL
==================================================

Enrich campaign insights with quantified business impact and ranking.

We want each campaign insight to answer:
- How big is this problem/opportunity?
- How much revenue is affected?
- What is the estimated leakage or upside?
- Which campaign insight should be fixed first?

==================================================
ARCHITECTURAL RULES
==================================================

1. Do NOT hardcode this logic in Streamlit pages.
2. Do NOT break the existing campaign analysis flow.
3. Add a thin post-processing enrichment layer after campaign analysis.
4. The enrichment layer must be deterministic and based only on existing campaign metrics, signals, and insights.
5. If some fields are missing, fail gracefully and still return usable output.
6. Use type hints, concise docstrings, small functions, and readable code.

==================================================
FILES TO ADD OR UPDATE
==================================================

Create or update only these files if needed:

app/services/campaign_insight_enricher.py
app/services/dashboard_service.py

You may also make minimal safe updates to:
app/services/campaign_analyzer.py

Do NOT modify Streamlit pages yet unless required for compatibility.

==================================================
1. CREATE A CAMPAIGN INSIGHT ENRICHER
==================================================

Create:
app/services/campaign_insight_enricher.py

Implement deterministic enrichment for campaign insights.

Expected main function:

def enrich_campaign_insights(
    campaign_results: list[dict],
) -> list[dict]:
    ...

Input:
- campaign_results from the existing campaign analyzer
- each campaign result already contains:
  - campaign
  - metrics
  - signals
  - insights
  - summary

Output:
Return a flattened list of enriched campaign insights.

Each enriched campaign insight must include:

{
  "campaign": "web",
  "title": "Discount becoming default sales mechanism",
  "summary": "...",
  "implication": "...",
  "action": "...",
  "priority": "high",
  "category": "pricing",
  "signal_code": "HIGH_DISCOUNT_DEPENDENCY",
  "revenue": 26130.18,
  "net_revenue": 26038.29,
  "orders": 437,
  "aov": 59.58,
  "discount_rate": 0.0595,
  "impacted_revenue": 26130.18,
  "estimated_loss": 0.0,
  "opportunity_size": 0.0,
  "priority_score": 82.5,
  "rank": 1,
  "why_now": "This campaign represents a large share of revenue and shows a pricing-related risk."
}

==================================================
2. BUSINESS IMPACT LOGIC
==================================================

Implement lightweight valuation logic using profit-proxy / revenue-proxy, not true profit.

Do NOT require ads spend or COGS.

For each insight, calculate these fields when possible:

A. impacted_revenue
- default: campaign revenue
- if product/entity-specific insight later exists, allow partial impacted revenue
- for now, use campaign revenue for overall campaign-level insights

B. estimated_loss
Use deterministic rules by insight/signal category.

Suggested proxy logic:

1. high discount dependency / pricing issue
- target_discount_rate = 0.15
- estimated_loss = max(discount_rate - target_discount_rate, 0) * revenue

2. stacked discounting
- estimated_loss = revenue * min(discount_rate, 0.10)
- keep conservative

3. low AOV / order value structure issue
- target_aov = 65.0
- opportunity_size = max(target_aov - aov, 0) * orders
- estimated_loss can remain 0 if not directly a leakage

4. refund / return issue
- if refunded_amount or refund rate is available, use that as estimated_loss
- otherwise leave 0 safely

5. source concentration / campaign concentration risk
- estimated_loss = 0
- opportunity_size = 0
- but still assign a high priority score if revenue is large

6. volume-driven growth / low quality growth
- opportunity_size = revenue * 0.03 as conservative proxy
- only if revenue_growth > 0 and aov_growth <= 0 signals are present

If no suitable formula exists:
- estimated_loss = 0
- opportunity_size = 0

Also calculate:
- affected_revenue_share = impacted_revenue / total_campaign_revenue_in_view
- use 0 safely if total is zero

==================================================
3. PRIORITY SCORING
==================================================

Implement a deterministic priority scoring model.

Expected output:
- priority_score as a float from 0 to 100
- rank assigned after sorting descending

Suggested scoring components:

A. revenue impact score (0-40)
- based on affected_revenue_share

B. severity score (0-25)
- high = 25
- medium = 15
- low = 8

C. leakage/opportunity score (0-25)
- based on estimated_loss + opportunity_size relative to total campaign revenue in view

D. strategic urgency score (0-10)
- pricing / discount / refund issues = 10
- growth quality / AOV / concentration = 7
- hygiene / informational = 4

Formula suggestion:
priority_score =
    revenue_impact_score
  + severity_score
  + leakage_score
  + urgency_score

Clamp to 100 if needed.

After scoring:
- sort descending
- assign rank starting from 1

==================================================
4. WHY_NOW FIELD
==================================================

Generate a short deterministic why_now sentence for each enriched insight.

Examples:
- "This campaign represents 94.0% of revenue in view and exceeds the target discount rate."
- "This campaign has sub-target AOV across 437 orders, making the issue scalable."
- "This is a high-severity pricing issue on one of the largest campaign buckets."

Do NOT use any LLM calls.
Keep it deterministic and concise.

==================================================
5. SIGNAL / INSIGHT MAPPING
==================================================

Map existing insight/signal types into valuation categories.

Support matching using either:
- insight_code
- signal_code
- title keywords
- category keywords

Handle these categories if possible:
- pricing
- growth_quality
- aov_structure
- refund
- concentration
- data_hygiene

Do not fail if some codes differ in the current codebase.
Use robust matching with helper functions.

==================================================
6. DASHBOARD SERVICE INTEGRATION
==================================================

Update:
app/services/dashboard_service.py

Requirements:

- Preserve existing dashboard behavior
- Keep existing campaign_summary_table
- Keep existing top_campaign_insights if needed, but enrich it
- Add or replace campaign insight output with enriched results

Suggested additional dashboard fields:

enriched_campaign_insights: list[dict]
top_campaign_insights: list[dict]   # now enriched + ranked
campaign_opportunity_summary: dict

campaign_opportunity_summary example:
{
  "total_estimated_loss": 1556.24,
  "total_opportunity_size": 932.18,
  "top_priority_campaign": "web",
  "top_priority_title": "Discount becoming default sales mechanism"
}

For top_campaign_insights:
- return the top 10 enriched insights sorted by priority_score desc

==================================================
7. DISPLAY-FRIENDLY OUTPUT SHAPE
==================================================

Make the enriched insight rows easy for Streamlit to display later.

Each row should be render-ready and include at minimum:

- campaign
- title
- priority
- category
- signal_code
- revenue
- net_revenue
- orders
- aov
- discount_rate
- impacted_revenue
- estimated_loss
- opportunity_size
- priority_score
- rank
- why_now
- summary
- implication
- action

Round numeric display fields reasonably but keep internal calculations stable.

==================================================
8. SAFETY / QUALITY RULES
==================================================

- Use type hints
- No TODO placeholders
- No pseudo-code
- No DB writes
- No Streamlit logic
- No hidden dependencies
- Keep functions pure
- Handle missing values safely
- Code must be directly runnable in current architecture

==================================================
9. OUTPUT FORMAT
==================================================

Return:
1. each file path changed
2. full code for each changed file
3. brief explanation per file
4. preserve existing imports and style where possible

==================================================
SUCCESS CRITERIA
==================================================

The implementation is successful if:

- /Campaigns can later display insight rows with quantified impact
- insights are ranked by business importance, not only listed
- the top items clearly communicate what is at stake
- the existing architecture remains intact
- no store-level logic is broken