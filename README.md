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

## Phase 2 status: Steam Market Analytics — complete

Phase 2 builds the structured-data analytical story of the Steam marketplace: evolution of the catalog over time, supply-side crowding and concentration, current pricing structure, and player reception/popularity across market segments — all descriptive, cohort-aware, and free of causal claims. See:

- `notebooks/02_market_analytics.ipynb` — the full walkthrough (11 figures, organized around 4 research questions rather than individual columns)
- `outputs/phase2_market_findings.md` — the written findings, evidence, and interpretation
- `figures/phase2/` — final figures
- `src/market_utils.py` — reusable Phase 2 transforms (built on top of `src/audit_utils.py`)
- `data/processed/games_clean.parquet` — a small (~8 MB), deterministic, normalized game-level table regenerated from `steam_games.csv` (documented in the notebook; not treated as ground truth for coarse fields like ownership)

**Five strongest findings:**

1. **Catalog growth is compositional, not uniform.** Comparing 2014-2016 to 2023-2025 release cohorts (catalog grew ~7.2x overall), Free To Play releases grew ~14.3x and Early Access ~10.3x, while Action (~5.8x) and Strategy (~6.4x) grew slowest — Action's and Strategy's *share* of releases actually declined even as absolute counts rose. The free-release share climbed from 3.5% (2010) to ~26% (2024-2025).
2. **Steam's catalog supply is highly fragmented, not publisher-dominated.** Across 86,963 unique developers and 73,219 unique publishers, ~77% of each appear in only one catalog record, and the top-10 developers combined hold just 1.1% of all developer-game links (a *catalog/release-count* concentration measure, not revenue).
3. **Extreme prices (up to $107,500) are explainable, not data errors** — a mix of deliberate novelty/shock listings and legitimate professional creative-software titles sold through the game storefront (e.g. Houdini Indie, VEGAS Edit). Typical pricing is far more modest: median paid price $5.99, 90th percentile $19.99.
4. **A genre's all-time popularity ranking can fully invert once release cohort is controlled for.** Massively Multiplayer has the highest all-time median review count of any major genre (17) — driven by a handful of long-lived legacy titles — but the 2023-2024 release cohort's MMO median collapses to 1, the lowest of any genre shown. This is the clearest demonstration in the project so far of why cumulative outcomes must be read cohort-aware.
5. **Most of the catalog receives very little observable player attention.** 40.3% of all games have zero recorded reviews and 59.2% have fewer than 10 — consistent with Phase 1's finding that `estimated_owners` is bottom-heavy (~82% in its lowest one or two buckets).

**Key methodological carryovers preserved from Phase 1** (still binding for Phase 2 and beyond):

- The companion `steam_games_reviews.csv` file contains critic/press pull-quotes, not player reviews, and was **not used** in Phase 2.
- `genres`/`categories`/`estimated_owners` required normalization for two mixed serialization formats found in Phase 1 (`src/audit_utils.py` parsers, reused throughout Phase 2).
- `price`, `estimated_owners`, `positive`/`negative`, `recommendations`, `peak_ccu`, and `average_playtime_forever` remain current-snapshot/cumulative values, not launch-time values — every Phase 2 finding above is framed accordingly (e.g. "current price," never "launch price").

**Roadmap note:** Phase 2's cohort-confound finding (point 4 above) reinforces Phase 1's temporal-leakage caution — any future success-modeling work must condition on release cohort as a first-class variable, not an afterthought. See `outputs/phase2_market_findings.md` § Implications for Later Phases for the fuller rationale.

## Phase 3 status: Success Definition & Temporal Framing — complete

Raw cumulative "success" is not directly usable in a single current-snapshot dataset: fields like `estimated_owners`, review counts, and `peak_ccu` mostly measure how long a game has been listed, not how well it did. Phase 3 is a methodological investigation (no model trained) that worked out whether — and exactly how — this dataset can support a defensible target for later modeling. See:

- `notebooks/03_success_definition_and_temporal_framing.ipynb` — the full investigation, structured as problem → candidate approaches → evidence → decision (not a column-by-column EDA)
- `outputs/phase3_success_definition.md` — the decision report (candidate evaluation, cohort-normalization experiments, final target/framing, and the decision gate)
- `outputs/phase3_leakage_map.csv` — field-by-field leakage ruling for the recommended target
- `figures/phase3/` — 7 diagnostic figures, each tied to a specific methodological question
- `data/processed/modeling_frame.parquet` — the recommended modeling population (2017-2023, n=67,241) with target and leakage-safe predictors attached, `outcome_*`-prefixed columns marked audit-only

**How Phase 3 addressed release-cohort bias:** Phase 2 showed raw popularity comparisons can be badly confounded by exposure time (the Massively Multiplayer example above). Phase 3 quantified this directly — raw `total_reviews` correlates with game age at Spearman rho = 0.569 — and tested three fixes: release-year cohort percentile (rho drops to 0.011), release-quarter percentile (equivalent, smaller cohorts), and a rolling ±90-day window, which was **tested and rejected** after it introduced a worse artifact of its own (rho = -0.392) caused by boundary truncation near the snapshot date.

**Success definition chosen:** popularity/visibility (`total_reviews`, cohort-relative) and player reception (`positive_ratio`, support-thresholded) are kept as two separate, non-combined constructs — a composite score was tested and rejected as adding noise rather than information. No engagement-based target survives (playtime fields are >90% zero regardless of transformation).

**Decision: GO for a narrowly-scoped supervised classification task** — see `outputs/phase3_success_definition.md` for the full specification. In one sentence, the defensible claim is: *using observable store/catalog metadata, estimate whether a 2017-2023-released game ranks among the top 20% highest-visibility titles within its own release-year cohort* — a claim about relative, cohort-conditioned observed player attention, explicitly **not** about revenue, launch-day success, or player satisfaction.

**What Phase 4 will actually claim:** a classifier trained on non-leaking, largely-static metadata (genre, category, platform, developer/publisher identity, release timing, current price with its ambiguity noted), evaluated with a chronological split (train 2017-2021 / validate 2022 / test 2023, test period untouched during development), predicting cohort-relative visibility — not success, and not anything requiring a historical snapshot this dataset doesn't have.

**Downstream project design (NLP scope, recommendation approach) beyond what Phase 3 fixed is intentionally still provisional and is not finalized in this README** — see the feasibility summary and Phase 3 decision report for the current recommended roadmap.

## Phase 4 status: Cohort-Aware Visibility Modeling — complete

The project's first predictive-modeling phase, built strictly on Phase 3's target/population/leakage decisions (not re-derived). See:

- `notebooks/04_cohort_aware_visibility_modeling.ipynb` — the full experiment: question → leakage-safe setup → baselines → feature-family ablation → model selection → freeze → one-time test evaluation → interpretation → limitations
- `outputs/phase4_modeling_results.md` — the full results writeup
- `outputs/phase4_feature_manifest.csv` — every model feature traced to a source column and a leakage/temporal-status ruling
- `figures/phase4/` — 7 figures, each tied to a specific modeling decision

**Exact modeling question:** using observable store/catalog metadata, estimate whether a 2017-2023-released Steam game ranks among the top 20% highest-visibility titles (by total review count) within its own release-year cohort. **Chronological split:** train 2017-2021 (n=40,448) → validate 2022 (n=12,255) → test 2023 (n=14,538, evaluated once, untouched during development).

**Final model:** LightGBM on a deliberately "conservative" feature set — genre/category, platform, release timing, point-in-time developer/publisher release history, and static store metadata (90 features, no missing values, no imputation needed). **Strongest results:** validation ROC-AUC 0.811 / PR-AUC 0.577; test (2023) ROC-AUC 0.801 / PR-AUC 0.553 — a small, honestly-reported drop consistent with real one-year-ahead chronological generalization, not overfitting.

**Feature-ablation insight worth keeping:** a "broader snapshot" model that adds current price, achievements, language count, and community tags scores substantially higher (test-adjacent validation ROC-AUC 0.911) — but a large share of that gain traced back to features that are themselves partly *downstream of* popularity rather than independent of it. One category value, `Steam Trading Cards`, turned out to be an almost pure popularity proxy (Valve's card program has historically been gated by player engagement) and was removed outright; Steam tags require a minimum player-vote threshold before they even appear on a store page, so "having tags at all" is itself a faint popularity signal. The conservative model was selected as the frozen, tested model specifically because of this finding — higher validation performance was not treated as automatically better.

**Limitation worth keeping:** validation error analysis shows the model's clearest blind spot is exactly what intuition would predict — budget-priced indie breakout hits from first-time developers are over-represented among high-confidence false negatives (Indie: 74% of misses vs. 64% overall). This is consistent with (not proof of) missing factors this dataset simply does not contain: marketing, franchise strength, gameplay quality, streamer/press attention, and wishlist momentum.

**What this model does not claim:** commercial success, revenue, player satisfaction, pre-launch prediction, or any causal account of what drives visibility. It ranks *relative, cohort-conditioned, observed player attention* — nothing stronger.

## Repository structure

```
steam-games-intelligence/
├── README.md
├── requirements.txt
├── .gitignore
├── notebooks/
│   ├── 01_data_audit_and_feasibility.ipynb
│   ├── 02_market_analytics.ipynb
│   ├── 03_success_definition_and_temporal_framing.ipynb
│   └── 04_cohort_aware_visibility_modeling.ipynb
├── src/
│   ├── audit_utils.py           # reusable parsing utilities discovered during the audit
│   ├── market_utils.py          # Phase 2 transforms (price tiers, cohort/genre helpers, games_clean builder)
│   └── modeling_utils.py        # Phase 4 transforms (multi-hot encoding, point-in-time prior counts, metrics)
├── figures/
│   ├── phase1/                  # diagnostic figures referenced in the audit
│   ├── phase2/                  # final market-analytics figures
│   ├── phase3/                  # success-definition / temporal-framing diagnostic figures
│   └── phase4/                  # visibility-modeling figures (ablation, calibration, error analysis, etc.)
├── data/
│   ├── raw/                     # place steam_games.csv / steam_games_reviews.csv here (gitignored)
│   └── processed/
│       ├── games_clean.parquet     # normalized game-level table, regenerated from steam_games.csv (see notebook 02)
│       └── modeling_frame.parquet  # 2017-2023 modeling population + target + leakage-safe predictors (see notebook 03)
└── outputs/
    ├── feasibility_summary.md
    ├── feature_role_audit.csv
    ├── join_summary.csv
    ├── phase2_market_findings.md
    ├── phase3_success_definition.md
    ├── phase3_leakage_map.csv
    ├── phase4_modeling_results.md
    ├── phase4_feature_manifest.csv
    ├── phase4_ablation_results.csv
    ├── phase4_validation_metrics.csv
    └── phase4_test_metrics.csv
```

## Setup

```bash
pip install -r requirements.txt
jupyter notebook notebooks/01_data_audit_and_feasibility.ipynb
```
