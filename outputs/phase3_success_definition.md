# Phase 3 — Defining Success in a Current-Snapshot Dataset

Snapshot date: **2026-08-28**. This is a methodological decision document, not a model report — no predictive
model was trained in Phase 3. Full evidence, code, and figures: `notebooks/03_success_definition_and_temporal_framing.ipynb`, `figures/phase3/`, `outputs/phase3_leakage_map.csv`.

## Why Raw Success Is Problematic

This dataset is a single current-day cross-section. We do not have `reviews_at_6_months`, `owners_at_12_months`,
launch price, or any other fixed-horizon historical snapshot. Every popularity/outcome field
(`estimated_owners`, `positive`/`negative`, `recommendations`, `peak_ccu`, `average_playtime_forever`) is a
**current cumulative value**, so older games have simply had more time to accumulate it. Phase 2 demonstrated
this concretely: Massively Multiplayer games show the highest all-time median review count of any major genre
(17) but the lowest among 2023-2024 releases (median 1) — an exposure-time artifact, not a real signal. Any
target built on these fields without correcting for release timing would mostly be learning "how long has
this game been listed," not anything resembling success.

## Popularity, Reception, and Engagement Are Different

Three conceptual dimensions were evaluated against the actual data:

- **Popularity/visibility** (candidates: `total_reviews`, `estimated_owners`/`own_mid`, `peak_ccu`,
  `recommendations`) — measurable, but only `total_reviews` has both full coverage (0% missing) and enough
  granularity (5,910 distinct values) to be useful. `own_mid` collapses to only 14 distinct values, with
  66.3% of the catalog in one bucket; `peak_ccu` is 85.8% zero; `recommendations` is 21.9% missing plus 62.2%
  zero of what remains.
- **Player reception** (`positive_ratio`) — measurable only where review volume supports it; unstable at low
  counts (a 1-review game's ratio can only be exactly 0% or 100%).
- **Engagement** (`average_playtime_forever`, `median_playtime_forever`) — **not usable as a target**. Both
  are 91.4% zero regardless of transformation. Dropped entirely.

Testing whether popularity and reception move together (rather than assuming it): the overall Spearman
correlation between `total_reviews` and `positive_ratio` is small and slightly **negative** (rho = -0.073),
an artifact of the noisy 1-review bucket. Once support is adequate (2+ reviews), a mild **positive** gradient
emerges — median ratio rises from 80.0% (2-10 reviews) to 89.3% (10,000+ reviews), a real but modest ~9-point
spread. **Conclusion: popularity and reception are conceptually and empirically distinct and must not be
conflated into one scalar.**

## Candidate Outcome Evaluation

| Candidate | Measures | Strengths | Weaknesses | Temporal Risk | Verdict |
|---|---|---|---|---|---|
| `total_reviews` | Observed player attention/visibility | 0% missing, 5,910 distinct values, correlates 0.51-0.67 with alternatives without being redundant | Extremely right-skewed; not a revenue/ownership measure | High (raw); resolved by cohort-percentile framing | **Primary popularity target** |
| `estimated_owners` (`own_mid`) | Coarse ownership reach | Directionally meaningful cross-check | Only 14 distinct values; 66.3% of catalog in one bucket | High; and too coarse for cohort framing to help much | Secondary cross-check only |
| `peak_ccu` | Peak concurrent players | Directly measures live engagement intensity | 85.8% zero | High (all-time cumulative maximum) | Rejected — too sparse |
| `recommendations` | Steam's own recommendation count | Conceptually close to reviews | 21.9% missing, 62.2% zero of remainder | High (cumulative) | Rejected — too sparse/incomplete |
| `positive_ratio` | Player reception among those who reviewed | Interpretable percentage; shrinkage available for low counts | Unstable below ~10 reviews; conditions on having enough reviews to compute at all | Moderate (denominator is itself cumulative) | Secondary target — descriptive/association use only, not supervised |
| `average_playtime_forever` / `median_playtime_forever` | Engagement | N/A | 91.4% zero | High | Rejected — no usable signal |

## Exposure-Time Analysis

Restricted to the 2010-2025 dated population (n = 121,300): raw `total_reviews` correlates strongly with
`age_days` (Spearman rho = **0.569**) — exactly the confound Phase 2 flagged. Three cohort-normalization
methods were built and compared directly against this raw relationship.

## Cohort-Normalization Experiments

| Method | Spearman rho vs. age_days | Verdict |
|---|---|---|
| Raw `total_reviews` | 0.569 | Confound confirmed |
| Release-year percentile | **0.011** | Effectively eliminates the confound; simple, large cohorts |
| Release-quarter percentile | -0.011 | Equally effective; smaller cohorts (min n = 47), no measurable benefit over year-level here |
| Rolling ±90-day cohort | **-0.392** | **Rejected** — introduces a worse, opposite-direction artifact |

The rolling-window result required diagnosis, not just reporting: the newest games in the tested population
(released late 2025) showed a median rolling-cohort percentile of 0.97 — near the top — purely because their
±90-day comparison window is truncated at the data's right-censoring boundary (no 2026 games were in the
tested population), leaving them compared only against an equally-under-reviewed sliver of other very-recent
releases. This is a structural property of rolling windows applied to a right-censored snapshot, not a
dataset-specific bug, and it would recur at whatever boundary a live snapshot uses. **Release-year percentile
is the recommended cohort-normalization method** — it matches the quarter-level method's de-confounding power
with larger, simpler, more stable cohorts, and avoids the rolling method's boundary artifact entirely.

**Important caveat:** cohort normalization *reduces* the raw age relationship from rho 0.569 to 0.011 — it
does not, and cannot, eliminate every temporal effect (e.g. within-cohort seasonality, slower catalog-wide
discoverability shifts). It only removes the dominant confound: raw exposure-time accumulation.

## Reception Support / Shrinkage Analysis

Minimum-review thresholds of 1, 5, 10, 20, 50, and 100 were compared on coverage, `positive_ratio` variance,
and genre representation. Standard deviation falls fastest between 1 and 10 reviews (0.239 → 0.179) and much
more slowly afterward (0.179 → 0.147 from 10 to 100), while coverage keeps dropping steadily (59.7% → 16.4%
of the catalog). Genre representation drops from 33 of 43 observed genres (at ≥1 review) to 28 (at ≥5
reviews) and then stays flat through ≥100 — raising the threshold further costs sample size, not genre
diversity. **Threshold selected: `total_reviews >= 10`**, matching the choice already made in Phase 2, for any
descriptive `positive_ratio` comparison.

A simple Laplace/Beta-style shrinkage estimator was also built and evaluated: `shrunk_ratio = (positive + k *
global_mean) / (total_reviews + k)` with `k = 10` pseudo-reviews at the catalog-wide mean rate (75.8%). For
1-review games, this collapses the raw {0%, 100%} coin-flip (std 0.465) to a tight band around the prior (std
under 0.05); for 200+-review games it barely moves the ratio (mean absolute shift < 0.005). **Decision:**
prefer `shrunk_ratio` when low-review games cannot be excluded; prefer the simpler thresholded-raw ratio
(`total_reviews >= 10`) otherwise, since the two are nearly identical once that threshold is already applied.

## Composite Metric Decision

Tested directly rather than assumed: `total_reviews` and `own_mid` are correlated enough (rho = 0.67 on the
full catalog, 0.57 among reviewed games) that averaging them would mostly add the coarser field's noise to
the finer one, not new information. `positive_ratio` correlates only weakly and non-monotonically with
`total_reviews` (rho = -0.07 raw, mild positive gradient only once support is adequate) — a genuinely
different construct. **Decision: no composite success score.** Popularity (`total_reviews`, cohort-relative)
and reception (`positive_ratio`, support-thresholded) remain two separate, non-combined measures; no weights
were invented.

## Recommended Modeling Population

**2017-01-01 through 2023-12-31.** Excludes:
- **2026** — partial year (through 2026-08-28 at time of snapshot), cannot be ranked against completed years.
- **2024-2025** — insufficient settling time (38.1% and 76.6% zero-review share respectively; the median 2025
  release has literally zero recorded reviews).
- **Pre-2017** — Steam Direct replaced Greenlight in mid-2017, a documented structural break in how games
  reach the storefront, and Phase 2 independently found catalog composition (genre mix, F2P/Early-Access
  share) shifting sharply from around this point — pre-2017 cohorts describe a materially different
  marketplace regime despite their excellent signal quality (<2% zero-review share).

Resulting population: n = 67,241, with per-year cohort sizes from 5,918 (2017) to 14,538 (2023) — large
enough for stable percentile computation throughout. This population, the target defined below, and the
Task 13 predictor survivors are materialized in `data/processed/modeling_frame.parquet` (n = 67,241 rows,
25 columns, ~5.3 MB) for direct reuse in Phase 4 — `outcome_*`-prefixed columns are included for audit/
transparency only and must be dropped before training any model on this frame.

## Recommended Target

**Binary classification: does the game rank in the top 20% of `total_reviews` within its own release-year
cohort?** Regression on the continuous cohort percentile was evaluated as a more information-preserving
alternative and remains a legitimate secondary framing for Phase 4 to consider; ranking/ordinal framing was
evaluated and found to reduce, in practice, to the same thing as percentile regression with added modeling
complexity and no clear benefit for this dataset. Classification was chosen as the primary framing because it
maps directly onto the plain-language prediction claim below and because per-cohort class balance is
extremely stable by construction (top-20% ranged 19.79%-20.08% across all seven modeling-eligible years).
Top 20% was chosen over top 10% (thinner positive class for a metadata-only predictor set) and top 25%
(starts to blur into "above-average" rather than "clearly high-visibility") — this is a starting
recommendation for Phase 4 to pressure-test, not a claim that 20% is uniquely correct.

## Leakage Exclusions

Full field-by-field ruling: `outputs/phase3_leakage_map.csv` (36 rows across the visibility and reception
target candidates). Summary for the recommended visibility target (34 fields evaluated): 3 **critical**
exclusions (`positive`, `negative`, raw `total_reviews` — the target's own components), 7 **high**-risk
exclusions (`positive_ratio`, `recommendations`, `peak_ccu`, `estimated_owners`/`own_mid`,
`steam_store_available`, and naive full-dataset developer/publisher track-record counts), 9 **moderate**-risk
exclusions or cautions (post-launch cumulative fields, `price`/`price_status` with a current-vs-launch
caveat), and 9 **low**-risk fields safe to include (`genres`, `categories`, developer/publisher identity,
platform flags, description text as metadata only).

**Confirmed, not assumed:** a naive "developer's total game count" feature computed over the full dataset
would leak future release information for 73.9% of multi-game-developer rows, overstating true prior track
record by roughly 2x on average (6.75 true prior releases vs. 13.50 shown by the naive count). Any developer/
publisher track-record feature in Phase 4 must be built using only releases strictly before each target
game's `release_date`.

## Recommended Validation Strategy

**Chronological split: train on 2017-2021 (n = 40,448), validate on 2022 (n = 12,255), test on 2023 (n =
14,538, held out).** A random split would let the model see games released after some test-set games,
reintroducing at the whole-dataset level the same kind of leakage Task 13 diagnosed for individual features.
2023 is the most recent year that still clears the signal-maturity bar (33.6% zero-review share) established
above, making it the natural final holdout. **The 2023 test period must remain untouched during all Phase 4
model development, feature engineering, and threshold selection** — 2022 is available for that iteration
instead.

## Exact Defensible Prediction Claim

> *"Using observable store/catalog metadata (genre, category, platform support, release timing,
> developer/publisher identity, and current price with its ambiguity noted), estimate whether a 2017-2023-
> released Steam game is likely to rank among the top 20% highest-visibility titles (by total review count)
> within its own release-year cohort."*

This is a claim about relative, cohort-conditioned, **observed player attention** — not revenue, units sold,
critical quality, or launch-day success.

## Claims We Must Not Make

- "Predict whether a new Steam game will become successful before launch" — no fixed-horizon, leakage-free
  pre-launch feature set exists, and "success" itself does not reduce to one measurable construct.
- "Predict a game's future review count or ownership" — this is a single cross-section; there is no
  earlier-snapshot ground truth to validate any forward-looking claim against.
- "Predict positive review ratio / player satisfaction" — reception requires adequate review support to even
  compute, which already conditions the target on having achieved a level of popularity (a selection-on-
  outcome problem, not solved by the same fix as the visibility target).
- "Identify what makes a game successful" — no causal inference is performed at any phase of this project;
  every finding here is a descriptive, cohort-conditioned association.

## Phase 4 Recommendation

Build the classification task specified above: top-20%-within-release-year-cohort visibility, on the
2017-2023 population, with the chronological train/validate/test split and the leakage exclusions in
`outputs/phase3_leakage_map.csv` strictly enforced. Treat `positive_ratio` as a descriptive/association
analysis only (e.g. how reception varies by segment among adequately-reviewed games), not a second supervised
target. Expect a real but bounded predictive ceiling: the surviving predictor set (genre, platform, developer/
publisher identity, release timing, price with caveats, description length) describes catalog positioning,
not gameplay quality, marketing spend, or storefront placement — all plausible drivers of visibility that
this dataset simply does not contain.

## Decision Gate

**A. GO — SUPERVISED ML**, narrowly scoped as specified above (target, population, predictors, validation,
and claim all fixed in this document). This is a GO because the specific claim survived every rejection test
run against it in this notebook — the conflation check (popularity vs. reception), the cohort-normalization
test (raw vs. year vs. quarter vs. rolling), the composite-metric test, and the leakage audit — not because
the project was always intended to end in ML. Reception (`positive_ratio`) is explicitly **not** included in
this GO and remains MODIFY-scoped (descriptive/association analysis only), for the selection-on-outcome
reason stated above.
