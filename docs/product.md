# Product — AI Agent for Shopify promotion optimization

## Vision

Build AI agents that continuously grow profit for e-commerce businesses.

## Mission

Turn e-commerce businesses into autonomous profit engines through AI-driven decision systems.

## Current Phase

Phase 1: Decision support from CSV (human-in-the-loop)

## Current Capabilities

- Upload Shopify order CSV
- Parse orders + line items into a local DB
- Generate store-level metrics → signals → rules → narrated insights
- `/Campaigns`: compare campaign groups (UTM/landing/source/discount code) and show money-oriented insights + actions
  - PDF export (with a dependency-free local fallback)
- `/Discount`: per-SKU promo drafts with review workflow (Accept/Reject/Adjust) and JSON export / DB persistence
  - Level 2 (lite): velocity + confidence + segment policy
  - Level 3: promotion mix templates (`discount` / `bundle` / `flash_sale`) with editable parameters

## Not in scope (yet)

- No Shopify API integration
- No auto execution
- No real-time data
- No closed-loop measurement (recommend → execute → measure → learn) yet

## Next Step

- Wire Shopify execution (safe, gated) for approved drafts
- Add measurement + feedback loop to learn from outcomes
- Improve profit-aware impact estimates (COGS / margin assumptions)

