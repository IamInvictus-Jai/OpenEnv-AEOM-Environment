---
title: AEOM Environment Server
emoji: 🛒
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---

# AEOM — Autonomous E-commerce Operations Manager

An OpenEnv RL environment where an agent acts as a Level-2 customer support manager for a quick-commerce platform. The agent processes inbound tickets by querying a mock database, gathering evidence, and resolving claims via refund, reship, or denial — while strictly enforcing company policy.

---

## Environment Description

The environment simulates a Zepto/Blinkit-style backend operations system. Each episode is a multi-turn conversation between the agent and the environment. The agent must:

- Parse the customer's complaint
- Query a mock database (orders, customers, products)
- Collect required evidence (e.g. photo proof for damaged items)
- Calculate refund amounts where applicable
- Execute the correct resolution without violating policy

Policy rules are included in every observation so the agent never has to memorize them.

---

## Action Space

All actions are JSON objects with an `action` field:

| Action | Required Fields |
|---|---|
| `request_customer_info` | `field`: one of `order_id`, `email`, `reason`, `photo_evidence`, `delivery_address` |
| `query_database` | `collection`: `orders`/`customers`/`products`, `query`: `{field: value}` |
| `calculate_total` | `base_price`: float, `extra_fees`: float |
| `execute_resolution` | `resolution`: `refund`/`reship`/`deny`, `amount` (refund only), `wallet` (refund only), `reason` (deny only) |

Malformed or unknown actions return an `error_log` and a `-0.10` penalty.

---

## Observation Space

Each `step()` returns:

```json
{
  "ticket_status": "open | pending_customer | pending_db | resolved | denied | failed",
  "customer_reply": "<string | null>",
  "db_result": "<object | null>",
  "error_log": "<string | null>",
  "steps_taken": 3,
  "policy_snapshot": {
    "return_window_days": 7,
    "photo_evidence_required_for": ["damaged", "tampered"],
    "refund_wallet_options": ["source", "store_credit"],
    "delivery_fee_refundable": true,
    "platform_fee_refundable": false
  }
}
```

---

## Tasks

### Task 1 — standard_refund (Easy)
Customer reports a missing order and provides the Order ID upfront. Agent must query the database and issue a refund.

Expected score range: `0.55 – 1.00`

### Task 2 — damaged_item_refund (Medium)
Customer reports a damaged item but provides no Order ID. Agent must request the ID, request photo evidence (policy requirement), calculate base price + delivery fee, then refund.

Expected score range: `0.30 – 1.00`

### Task 3 — policy_violation_denial (Hard)
Customer requests a refund for an order placed outside the 7-day return window. No Order ID given. Customer applies social pressure claiming a prior agent promised a refund. Agent must look up by email, verify the order date, and deny the claim citing policy — without being manipulated.

Expected score range: `0.10 – 0.80`

---

## Reward Function

Dense partial rewards ranging from `0.0` to `1.0`. The agent earns fractional credit for correct intermediate steps (querying the right collection, requesting required evidence, calculating the correct total) and is penalized for bad actions. Final score is set at `execute_resolution`.

Penalties include: malformed actions (`-0.10`), redundant info requests (`-0.05`), resolving before gathering required evidence (`-0.15`), wrong resolution type (`-0.20`).

---

## Setup

```bash
pip install openenv-core
git clone <your-repo>
cd aeom_env
pip install -e .
```

Start the server:
```bash
python -m uvicorn aeom_env.server.app:app --host 0.0.0.0 --port 8000
```

---

## Running Inference

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `HF_TOKEN` | Yes | Your Hugging Face API token (used as the LLM API key) |
| `API_BASE_URL` | Yes | LLM endpoint — defaults to HF Inference Router |
| `MODEL_NAME` | Yes | Model identifier for inference |
| `AEOM_SEED` | No | Random seed for reproducible episodes (default: `42`) |
| `IMAGE_NAME` | No | Local Docker image name — leave empty to use the live HF Space |
| `ENV_URL` | No | Override the environment server URL (default: HF Space URL) |

Then run:
```bash
python inference.py
```

By default `inference.py` connects to the live HF Space at `https://invictus-jai-aeom-env.hf.space`. Set `IMAGE_NAME` to run against a local Docker container instead.

---

## Docker

```bash
docker build -t aeom_env:latest -f server/Dockerfile .
docker run -p 8000:8000 aeom_env:latest
```

---

## Baseline Scores (Qwen2.5-72B-Instruct, seed=42)

| Task | Difficulty | Score |
|---|---|---|
| standard_refund | Easy | 0.60 – 0.90 |
| damaged_item_refund | Medium | 0.70 – 1.00 |
| policy_violation_denial | Hard | 0.35 – 0.70 |
