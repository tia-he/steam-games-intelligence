# Steam Games Intelligence

A portfolio data science project exploring what can be learned from a snapshot of the Steam catalog — game metadata, market/pricing structure, critical reception, and (potentially) success factors and game-to-game similarity.

## Motivation

The guiding question is: **"What makes a Steam game successful, how do players/critics respond to games, and what can we learn from similar games?"**

This is a large, ambitious question, and the honest answer depends entirely on what the available data can actually support. Rather than assuming a fixed roadmap, this project starts with a rigorous data audit (Phase 1) and lets the findings determine which downstream modules are realistic.

## Dataset

Two raw CSV files, joined on `app_id`:

- **`steam_games.csv`** — ~139K rows, 42 columns of game metadata: pricing, genres/categories/tags, developer/publisher, review and popularity counts, playtime, platform support, store descriptions, and availability flags.
- **`steam_games_reviews.csv`** — ~13K rows (a subset of the games above) with a free-text `reviews` field. **Phase 1 found this field does not match its original documentation**: rather than up to ~100 structured user reviews per game, it contains a small number (median 3, max 10) of concatenated critic/press pull-quotes scraped from the Steam store page, with no structured per-review fields. See `outputs/feasibility_summary.md` for the full finding.

Both files are a **current snapshot** of a live, daily-updated dataset — not a historical record.

### Obtaining the raw data

The raw CSVs are not committed to this repository (they're large, and one is ~900 MB). Place them at:

```
data/raw/steam_games.csv
data/raw/steam_games_reviews.csv
```

## Methodological note: snapshot data and leakage risk

Because the data is a single current-day snapshot, fields like `estimated_owners`, `positive`/`negative` review counts, `recommendations`, and `average_playtime_forever` are **cumulative outcomes measured today**, not values known at each game's launch. Older games have had more time to accumulate owners, reviews, and playtime than newer ones — Phase 1 confirms this exposure-time effect is severe (see `figures/phase1/05_outcome_vs_release_year_exposure_time.png`). `price` is documented as current price and cannot be assumed equal to launch price. Any future "success prediction" work must treat this as a first-class constraint rather than an afterthought — see `outputs/feasibility_summary.md` for how each module is scoped around it.

## Phase 1 status: Data Audit & Feasibility — complete

Phase 1 audits both files empirically (not from documentation assumptions), checks join feasibility and coverage bias, audits temporal/leakage risk for candidate outcome variables, and issues a GO / MODIFY / DROP call for each proposed module. See:

- `notebooks/01_data_audit_and_feasibility.ipynb` — the full walkthrough
- `outputs/feasibility_summary.md` — the written findings and module-by-module recommendation
- `outputs/feature_role_audit.csv` — per-column role/leakage classification
- `outputs/join_summary.csv` — join coverage statistics
- `figures/phase1/` — diagnostic figures

**Downstream project design (NLP scope, success-modeling target, recommendation approach) is intentionally provisional and is not finalized in this README** — it is driven by the Phase 1 findings, which found the review data and success-outcome variables to be materially different from what was originally assumed. See the feasibility summary for the current recommended roadmap changes.

## Repository structure

```
steam-games-intelligence/
├── README.md
├── requirements.txt
├── .gitignore
├── notebooks/
│   └── 01_data_audit_and_feasibility.ipynb
├── src/
│   └── audit_utils.py          # reusable parsing utilities discovered during the audit
├── figures/
│   └── phase1/                 # diagnostic figures referenced in the audit
├── data/
│   ├── raw/                    # place steam_games.csv / steam_games_reviews.csv here (gitignored)
│   └── processed/              # (empty in Phase 1)
└── outputs/
    ├── feasibility_summary.md
    ├── feature_role_audit.csv
    └── join_summary.csv
```

## Setup

```bash
pip install -r requirements.txt
jupyter notebook notebooks/01_data_audit_and_feasibility.ipynb
```
