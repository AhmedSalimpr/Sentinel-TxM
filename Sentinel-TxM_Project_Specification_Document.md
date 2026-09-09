# Project Specification Document

## Project Sentinel-TxM
### Transaction Monitoring & Graph Analytics Engine

**Document Version:** 1.0
**Author:** [Your Name]
**Date:** July 2026
**Status:** Draft — Portfolio Project

---

## 1. Executive Summary

Project Sentinel-TxM is an open-source, portfolio-grade financial crime detection system that simulates a modern FinTech transaction monitoring pipeline. It ingests synthetic payment data, applies rule-based and graph-based detection logic to identify structuring (smurfing) and money mule network typologies, and surfaces the results through a compliance analyst dashboard.

The project is designed to demonstrate, in a single cohesive codebase, both software engineering competency (clean architecture, decoupled services, APIs) and data analytics/FinCrime domain competency (time-series windowing, network analysis, risk scoring) — skills directly relevant to FinTech, RegTech, and financial crime analyst roles.

---

## 2. Objectives

| # | Objective | Success Measure |
|---|-----------|------------------|
| 1 | Demonstrate understanding of real-world FinCrime typologies | Correctly models structuring and mule-network patterns |
| 2 | Demonstrate data engineering skill | Efficient windowed/streaming-style processing at scale (100k+ transactions) |
| 3 | Demonstrate graph analytics skill | Working NetworkX-based hub/cycle detection |
| 4 | Demonstrate full-stack delivery | End-to-end pipeline from data generation to a usable dashboard |
| 5 | Be recruiter/interview-ready | Clean repo, README, architecture diagram, reproducible setup |

---

## 3. Scope

### 3.1 In Scope
- Synthetic data generation (users, transactions) with injected suspicious patterns
- Rule-based structuring detection (sliding time-window aggregation)
- Graph-based mule ring detection (hub-and-spoke, cycles)
- Alert generation and storage
- API layer to serve alerts and supporting data
- Analyst-facing dashboard (list view, risk profile, time-series chart, network graph visual)

### 3.2 Out of Scope
- Real user/customer data of any kind
- Production-grade authentication, multi-tenancy, or regulatory certification
- Real-time streaming infrastructure (Kafka, etc.) — simulated via batch/windowed processing instead
- Integration with live payment rails or third-party KYC providers

---

## 4. System Architecture

```
[ Data Generator ] ---> [ Ingestion Pipeline ] ---> [ Detection Engine ] ---> [ Alert Dashboard ]
 (Faker-based,           (DuckDB / Pandas             (Rules engine +           (FastAPI backend +
  synthetic users,        for windowed                 NetworkX graph            Streamlit/React
  KYC, multi-hop           aggregation)                 analytics)                analyst UI)
  transfers)
```

**Design principles:**
- **Decoupled components** — each phase can run, be tested, and be demoed independently.
- **Reproducibility** — a single command regenerates the full dataset and re-runs detection end to end.
- **Explainability** — every alert stores *why* it fired (rule triggered, threshold, contributing transactions), since explainability is a core requirement in real compliance systems.

---

## 5. Component Specifications

### 5.1 Phase 1 — Synthetic Data Generator

**Purpose:** Produce a realistic, labelled dataset for downstream detection logic to run against.

**Tech:** Python, `Faker`, `pandas`

**Data model:**

`users` table
| Field | Type | Notes |
|---|---|---|
| user_id | UUID | Primary key |
| kyc_status | enum | verified / pending / rejected |
| risk_score | float | 0–1, synthetic baseline risk |
| country_code | string | ISO country code |
| device_ip | string | Simulated login IP |

`transactions` table
| Field | Type | Notes |
|---|---|---|
| tx_id | UUID | Primary key |
| sender_id | UUID | FK to users |
| receiver_id | UUID | FK to users |
| amount | decimal | Transaction amount |
| currency | string | ISO currency code |
| timestamp | datetime | UTC |

**Requirements:**
- Generate a configurable volume of "normal" background transaction traffic.
- Inject a configurable number of **labelled** suspicious patterns, e.g.:
  - A sender making repeated transfers just under a reporting threshold within a short window.
  - A single device IP associated with multiple distinct accounts.
- Every injected pattern must carry a ground-truth label (e.g. `is_synthetic_smurf`, `is_synthetic_mule`) in a separate lookup table — this ground truth is used later to measure detection precision/recall, which is itself a strong talking point in interviews.

**Deliverable:** `generate_data.py` + `data/users.csv`, `data/transactions.csv`, `data/ground_truth.csv`

---

### 5.2 Phase 2 — Structuring (Smurfing) Detection Rule

**Purpose:** Detect attempts to evade reporting thresholds by splitting a large transfer into multiple smaller ones.

**Tech:** DuckDB or pandas

**Logic specification:**
- Sliding window: 3 days (configurable).
- Candidate transactions: individual amount within a configurable sub-threshold band (e.g. 85%–99.99% of a reporting threshold).
- Trigger condition: cumulative sum of a single sender's candidate transactions within the window exceeds a configurable total (e.g. 1.5–2x the reporting threshold).
- Output: write matching transaction groups to an `alerts` table with:
  - `alert_id`, `user_id`, `rule_name`, `window_start`, `window_end`, `total_amount`, `contributing_tx_ids`, `risk_weight`

**Deliverable:** `detect_structuring.py` + unit tests validating detection against the labelled synthetic patterns from Phase 1.

---

### 5.3 Phase 3 — Graph Analytics for Mule Rings

**Purpose:** Detect network-level laundering patterns that single-transaction rules miss.

**Tech:** NetworkX

**Logic specification:**
- Build a directed graph: nodes = `user_id`, edges = transactions (weighted by amount, timestamped).
- **Hub-and-spoke detection:** flag any node receiving inbound transfers from N or more distinct nodes (configurable, e.g. 5+) within a short time window (configurable, e.g. 12 hours), where a high proportion of received funds (configurable, e.g. 90%+) is transferred onward within a short follow-on window.
- **Cycle detection:** flag closed loops of transfers returning funds to an originating node, a classic layering pattern.
- Output: hub/cycle alerts appended to the same `alerts` table, with `rule_name = "mule_hub"` or `"mule_cycle"` and a reference to the subgraph involved.

**Deliverable:** `detect_mule_networks.py` + a saved subgraph export (e.g. GraphML or JSON) per alert, used later for dashboard visualisation.

---

### 5.4 Phase 4 — Compliance Alert Dashboard

**Purpose:** Present detection output the way a compliance analyst would actually use it.

**Tech:** FastAPI (backend), Streamlit or React (frontend)

**API endpoints (minimum):**
- `GET /alerts` — list active alerts with summary fields
- `GET /alerts/{alert_id}` — full detail: contributing transactions, risk profile, subgraph
- `GET /users/{user_id}/profile` — KYC status, risk score, transaction history summary

**Dashboard views:**
- Alert queue (sortable/filterable by risk weight, rule type, date)
- Customer risk profile panel
- Time-series chart of the transaction velocity spike that triggered a structuring alert
- Network graph visualisation of a mule ring alert (nodes = accounts, edges = money flow, hub highlighted)

**Deliverable:** `api/main.py`, `dashboard/app.py`, screenshots for the README.

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | End-to-end pipeline processes 100,000+ synthetic transactions in under a few minutes on a laptop |
| Code quality | Type-hinted Python, modular structure, docstrings, `pytest` coverage on detection logic |
| Reproducibility | `requirements.txt` / `pyproject.toml`, one-command setup (e.g. `make run` or `docker-compose up`) |
| Documentation | README with architecture diagram, setup instructions, and example alert walkthrough |
| Ethics/data safety | 100% synthetic data; README must state clearly that no real personal or transactional data is used |

---

## 7. Evaluation / Success Criteria

Since ground-truth labels are generated in Phase 1, the project can (and should) report actual detection performance:
- Precision and recall of the structuring rule against labelled smurfing patterns
- Precision and recall of the graph detection against labelled mule patterns
- False-positive rate on background "normal" traffic

Reporting these metrics honestly (including false positives) is itself a strong signal to reviewers — real compliance systems are judged on this trade-off.

---

## 8. Roadmap / Milestones

| Milestone | Deliverable | Suggested effort |
|---|---|---|
| M1 | Data generator + labelled ground truth | 2–3 days |
| M2 | Structuring detection + tests | 2–3 days |
| M3 | Graph-based mule detection + tests | 3–5 days |
| M4 | API + dashboard | 3–5 days |
| M5 | README, architecture diagram, demo screenshots, metrics writeup | 1–2 days |

---

## 9. Repository Structure (proposed)

```
sentinel-txm/
├── data_generator/
│   └── generate_data.py
├── detection/
│   ├── detect_structuring.py
│   └── detect_mule_networks.py
├── api/
│   └── main.py
├── dashboard/
│   └── app.py
├── tests/
├── data/
├── README.md
└── requirements.txt
```

---

## 10. Disclaimer

This project uses entirely synthetic, procedurally generated data. It is an educational/portfolio demonstration of financial crime detection *concepts* and is not intended for, and must not be used in, any production compliance environment without independent legal, regulatory, and risk review.
