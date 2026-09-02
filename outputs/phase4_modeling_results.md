# Phase 4 — Cohort-Aware Visibility Modeling

Full code, evidence, and figures: `notebooks/04_cohort_aware_visibility_modeling.ipynb`, `figures/phase4/`,
`outputs/phase4_feature_manifest.csv`, `outputs/phase4_ablation_results.csv`,
`outputs/phase4_validation_metrics.csv`, `outputs/phase4_test_metrics.csv`.

## Modeling Question

Does observable Steam store/catalog metadata contain meaningful predictive information about a game's
*relative visibility* (review-count rank) within its own release-year cohort — and does that relationship
generalize chronologically to newer releases? This is deliberately narrow: not "will a game succeed," not
"predict future review count," not a causal account of what drives visibility.

## Target & Population

Reused unchanged from Phase 3, not re-derived: binary target = top 20% of `total_reviews` within release-year
cohort; population = 2017-2023 releases (n = 67,241); prevalence ≈ 20.0% every year by construction. QC
confirmed row count, split sizes, and per-year prevalence all match the Phase 3 specification exactly, with no
duplicate `app_id`, no missing target, and no 2024-2026 rows present.

## Temporal Validation Design

Chronological split, never a random one: **train 2017-2021 (n=40,448), validate 2022 (n=12,255), test 2023
(n=14,538)**. The 2023 test set was touched exactly once, in the final evaluation cell, after every feature,
model, hyperparameter, and threshold decision was frozen.

## Leakage-Controlled Feature Set

Every candidate feature was checked against `outputs/phase3_leakage_map.csv` before inclusion. All
`outcome_*`-prefixed columns in `modeling_frame.parquet` (`total_reviews`, `positive`, `negative`,
`positive_ratio`, `own_mid`) were excluded outright, along with `recommendations`, `peak_ccu`,
`average_playtime_forever`, `steam_store_available`, and any developer/publisher **success-rate** history
(Task 12: this dataset only has current-snapshot outcomes, so "developer's historical top-20% rate" would
silently smuggle in 2026-observed information about earlier games — excluded on principle, not attempted).

**A leakage discovery beyond Phase 3's scope:** Phase 3 rated the `categories` family "low risk" in
aggregate, but one specific value — `Steam Trading Cards` — turned out to be a near-pure popularity proxy
(median 356 vs. 10 `total_reviews` for games with vs. without it; a 66% vs. 16% top-20% rate). Valve's Trading
Card program has historically been gated by a game's popularity/engagement, not freely chosen by developers at
launch like enabling Steam Cloud saves. **This single column was identified and dropped**; the rest of the
`categories` family was kept.

## Temporal-Status Breakdown of Included Features

| Status | Families | Count |
|---|---|---|
| **A: stable descriptive metadata** | genre/category, platform, release timing, static store metadata (description/title length, genre/category counts) | 90 features (conservative model) |
| **B: current-snapshot, temporally ambiguous** | current price, achievements, supported-language count, tags | +107 features (broader-snapshot model only) |
| **C: point-in-time engineered history** | developer/publisher prior-release count (max over multi-credit games), "has prior release" flag | 4 features (both models) |

`release_year` itself is excluded as a default predictor throughout (dataset-era-artifact risk, given the
target is already cohort-normalized and validation is chronological).

## Developer/Publisher Feature Implementation

`prior_release_count`: for each game, the count of that developer's (or publisher's) **strictly earlier**
releases, computed over the **full 139,076-row raw catalog** (not just the 2017-2023 population), so a studio
active since 2012 gets credit. Same-day releases never count each other (strict `<`). Multi-credit games use
`max` across credited developers/publishers. **Sanity checks, all passed:** zero same-day-release pairs
violate the strict-prior rule; zero first-ever releases show a nonzero prior count; a manual recount for a
high-volume developer matches the engineered feature exactly.

**Unseen-developer/publisher rates** (developer/publisher never appearing in the 2017-2021 training window at
all): **67.8% of 2022-validation games, 74.8% of 2023-test games** have an unseen developer;
**61.9%/69.0%** have an unseen publisher — expected given Phase 2's finding that ~77% of developers appear
only once in the whole catalog, and worth stating plainly since it means `prior_release_count` is
uninformative beyond "first credited release" for most newer-cohort games.

**No developer/publisher success-rate/reputation features were built.** A feature like "developer's historical
top-20% rate" would require knowing each earlier game's *outcome* at the time the later game launched — this
snapshot only has outcomes as observed on 2026-08-28, so that information is not legitimately available.
Excluded on principle per Task 12.

## Baselines

| Model | ROC-AUC | PR-AUC | Log Loss | Brier |
|---|---|---|---|---|
| Majority-class (constant) | n/a (no ranking) | n/a | — | — |
| Logistic Regression (genre/category + platform + release timing) | 0.7701 | 0.4648 | 0.4258 | 0.1348 |
| LightGBM (same feature subset) | 0.7801 | 0.5082 | 0.4131 | 0.1301 |

**Answer to the first modeling question, on its own:** yes — even the smallest defensible feature subset
clears the majority baseline's uninformative ranking by a wide margin, and LightGBM outperforms logistic
regression on the identical subset, confirming real nonlinear structure worth capturing.

## Feature-Family Ablation

Six cumulative steps, same model family (LightGBM, default hyperparameters) and same train/validation split
throughout:

| Feature Set | ROC-AUC | PR-AUC | Log Loss | Δ PR-AUC |
|---|---|---|---|---|
| 1. Genre/category + platform | 0.7821 | 0.5167 | 0.4112 | — |
| 2. + Release timing | 0.7801 | 0.5082 | 0.4131 | -0.0084 |
| 3. + Developer/publisher | 0.8008 | 0.5570 | 0.3969 | +0.0487 |
| 4. + Stable store metadata (**CONSERVATIVE**) | 0.8111 | 0.5765 | 0.3873 | +0.0196 |
| 5. + Current price | 0.8249 | 0.6238 | 0.3692 | +0.0473 |
| 6. + Ambiguous store metadata (**BROADER SNAPSHOT**) | 0.9112 | 0.7667 | 0.2858 | +0.1429 |

**Release timing adds nothing on its own** (slightly negative delta) — kept only because it's free and
static, not because it's load-bearing. **Developer/publisher point-in-time history is the first family with a
clearly substantial contribution.** **Step 6's large jump is not fully trustworthy as launch-available
signal**: beyond the removed Trading Cards column, its remaining gain leans heavily on `achievements` count
and community `tags` — and Steam tags require a minimum threshold of player votes before they appear on a
store page at all (confirmed directly: games with zero tags have a median of 0 `total_reviews` vs. 17 for
games with any tags; tag count correlates with `total_reviews` at Spearman rho = 0.34). A meaningful share of
Step 6's apparent predictive power is therefore itself downstream of player attention, not independent
information about it.

## Conservative vs Broader Snapshot Features

| Metric | Conservative | Broader Snapshot | Δ |
|---|---|---|---|
| ROC-AUC | 0.8111 | 0.9112 | +0.1000 |
| PR-AUC | 0.5765 | 0.7667 | +0.1901 |
| Precision@Top10% | 0.6827 | 0.8589 | +0.1762 |
| Precision@Top20% | 0.5226 | 0.6850 | +0.1624 |

**Decision: the CONSERVATIVE model is selected as the primary frozen model.** The broader model's higher
score is real, not noise — but per this project's stated methodology ("if performance changes substantially,
report the tradeoff rather than automatically choosing the higher-performing model"), and given the concrete
evidence that a material share of that gain rides on features partly downstream of player attention itself,
the conservative model's ROC-AUC ≈ 0.81 / PR-AUC ≈ 0.58 is the number this project stands behind as "static/
point-in-time metadata predicts cohort-relative visibility." The broader-snapshot model is reported
transparently but was **not** carried to the 2023 test set.

## Final Model Selection

LightGBM on the conservative feature set (90 features: genre/category, platform, release timing, developer/
publisher point-in-time history, static store metadata). A 5-configuration manual grid over learning rate,
`num_leaves`, `min_child_samples`, and subsampling fractions was evaluated on validation PR-AUC; the winning
configuration matched the default used throughout the ablation (`learning_rate=0.05, num_leaves=31,
min_child_samples=30, feature_fraction=0.8, bagging_fraction=0.8`), with `best_iteration=268` selected by
early stopping against validation AUC.

## Validation Performance

| Metric | Value |
|---|---|
| ROC-AUC | 0.8111 |
| PR-AUC | 0.5765 |
| Log Loss | 0.3873 |
| Brier | 0.1212 |
| Precision @ threshold | 0.5226 |
| Recall @ threshold | 0.5235 |
| F1 @ threshold | 0.5231 |
| Precision@Top10% | 0.6827 |
| Precision@Top20% | 0.5226 |

## Frozen Model Specification (fixed before touching 2023 test data)

- **Feature set:** Conservative (Ablation Step 4), 90 features, `category__Steam Trading Cards` dropped
  catalog-wide.
- **Preprocessing:** none required — no missing values in any conservative-model column (a developer/
  publisher prior-release-count of 0 for a first-time credit is a legitimate value, not an imputation).
- **Model:** LightGBM, binary objective, `learning_rate=0.05, num_leaves=31, min_child_samples=30,
  feature_fraction=0.8, bagging_fraction=0.8`, `num_boost_round=268`.
- **Trained on:** 2017-2021 only — no refit on 2022 validation data, keeping the frozen model and its
  threshold directly traceable to the validation-selected configuration.
- **Threshold policy:** probability cutoff = 80th percentile of 2022-validation predictions = **0.2874**
  (frozen number, reused unchanged on test — never recomputed against test data).

## 2023 Test Performance

| Metric | Value |
|---|---|
| ROC-AUC | 0.8008 |
| PR-AUC | 0.5526 |
| Log Loss | 0.3973 |
| Brier | 0.1249 |
| Precision | 0.5021 |
| Recall | 0.5318 |
| F1 | 0.5165 |
| Precision@Top10% | 0.6609 |
| Precision@Top20% | 0.5113 |

## Chronological Generalization

| Metric | Validation 2022 | Test 2023 | Δ |
|---|---|---|---|
| ROC-AUC | 0.8111 | 0.8008 | -0.0104 |
| PR-AUC | 0.5765 | 0.5526 | -0.0239 |
| Precision@Top10% | 0.6827 | 0.6609 | -0.0218 |
| Precision@Top20% | 0.5226 | 0.5113 | -0.0113 |
| F1 | 0.5231 | 0.5165 | -0.0065 |

Every metric degrades modestly, never collapses. **The honest headline: static/point-in-time metadata's
relationship to cohort-relative visibility generalizes one year forward with only a small expected drop —
not a guarantee it holds indefinitely, but not overfit to 2017-2022 either.**

## Calibration

Reliability curve (10 bins, 2022 validation) tracks the diagonal closely across the full probability range —
e.g. predicted 4.6% vs. observed 6.4% in the lowest bin (n=6,181), predicted 93.8% vs. observed 94.4% in the
highest (n=125). Brier score 0.1212 on validation, 0.1249 on test. **No post-hoc calibration (Platt/isotonic)
was applied** — the model's raw probabilities are already reasonably trustworthy as stated, per Task 15's
instruction to add recalibration only if clearly needed.

## Feature Importance / Interpretation

*Method note: SHAP was evaluated but is unusable in this environment (its `numba` dependency requires NumPy
≤2.1; this environment runs NumPy 2.4). LightGBM's native gain importance is used instead.*

**Feature-family importance (share of total gain):** genre/category 48.5%, static store metadata 31.8%,
developer/publisher 15.5%, release timing 2.6%, platform 1.8%.

**Top individual features:** `store__n_categories`, `store__about_description_length`, `category__Steam
Cloud`, `devpub__publisher_prior_release_count`, `devpub__developer_prior_release_count`,
`store__title_length`, `genre__Free To Play`, `category__Steam Achievements`.

**Does importance agree with the ablation?** Partially. Developer/publisher's substantial ablation
contribution (+0.049 PR-AUC) is echoed by a meaningful 15.5% gain share. Release timing's near-zero ablation
contribution is echoed by its near-zero (2.6%) gain share. But static store metadata shows a *larger* gain
share (31.8%) than its modest ablation delta (+0.020 PR-AUC) would suggest — a real, expected divergence: the
tree-building process finds *some* use for description/title length and category counts inside the full
model, but most of what they capture is redundant with genre/category, so removing the whole family costs
comparatively little at the validation-metric level. Both views are kept because they answer different
questions (what the model leans on vs. what's irreplaceable).

Every statement above describes **association with the model's predictions**, never a causal claim about what
makes a game visible.

## Error Analysis

Validation-only, before test was touched. High-confidence errors are rare (90 false positives + 398 false
negatives = 4.0% of validation) — consistent with the reasonable calibration above — but their composition is
not random:

- **False positives skew toward Free games** (42% of FP vs. 24% overall) **and experienced developers** (59%
  of FP vs. 39% overall) — the model over-trusts "promising free release from a track-recorded developer"
  cues that don't always pan out.
- **False negatives skew toward the cheapest paid tier** ($0.01-4.99: 47% of FN vs. 38% overall), **first-time
  developers** (66% of FN vs. 61% overall), and **Indie** genre (74% of FN vs. 64% overall) — the
  metadata-invisible surprise hits: a budget indie game from an unproven developer, breaking out despite
  nothing observable predicting it.

**Plausible missing factors** (consistent with this pattern, not confirmed by it): marketing spend,
franchise/IP strength, gameplay quality itself, external press/streamer coverage, pre-launch wishlist
momentum, and viral/social discovery. None are observed anywhere in this dataset.

## What the Model Can and Cannot Tell Us

**Can:** rank 2017-2023 Steam releases by predicted relative visibility using static, point-in-time-safe
catalog metadata, with real (if modest) discriminative power that survives one year of chronological
generalization, and reasonably calibrated probabilities.

**Cannot:** predict commercial success, revenue, or units sold; predict player satisfaction or quality;
predict a game's fate before launch (some included fields, like current price, were deliberately excluded
from the frozen model precisely because they aren't guaranteed launch-time values); explain *why* a game
becomes visible in any causal sense; account for marketing, IP strength, or external attention — the
strongest single message from the error analysis.

## Exact Claims This Model Supports

> *Using observable store/catalog metadata (genre, category, platform, release timing, point-in-time
> developer/publisher history, and static store copy), estimate whether a 2017-2023-released Steam game is
> likely to rank among the top 20% highest-visibility titles (by total review count) within its own
> release-year cohort.*

## Claims It Does NOT Support

- Predicting whether a new Steam game will "succeed."
- Predicting future commercial performance or revenue.
- Predicting future review counts at any fixed horizon.
- Predicting player satisfaction or review sentiment.
- Identifying causal drivers of visibility.
- Making any claim about games released before 2017 or after 2023, or about a marketplace whose structure has
  shifted materially from the training/validation period (Phase 2 already documented ongoing compositional
  shifts).

## Implications for the Project

The core methodological finding — that a substantial share of "current-snapshot" predictive power is itself
downstream of the popularity it's meant to predict (Trading Cards being the extreme case, tag-visibility
gating being the subtler one) — reinforces this project's standing caution from Phases 1-3: current-snapshot
convenience is not the same as launch-time legitimacy, and that distinction has to be checked at the
individual-feature level, not just the family level. This is a genuinely new finding Phase 4 contributes on
top of Phase 3's cohort-normalization work, not a restatement of it.

## Limitations

1. The target is relative current review visibility, not commercial success.
2. Review counts are current cumulative outcomes, not fixed-horizon measurements.
3. Release-year normalization reduces, but does not eliminate, temporal bias.
4. Metadata is a current snapshot; some included fields may differ from launch-time state even in the
   conservative model (Phase 1: genres/categories/store copy are "static, mostly" — not guaranteed unchanged).
5. Important determinants of visibility (marketing, IP strength, gameplay quality, external attention) are
   almost certainly missing from this dataset.
6. The developer/publisher ecosystem is highly fragmented — 67.8-74.8% unseen-developer rates in
   validation/test limit how much the model can lean on developer history for newer cohorts.
7. The model should not be interpreted causally.
8. Chronological generalization is tested only across one year-ahead holdout (test on 2023) — not a guarantee
   about generalization to 2024+ or to a structurally different future marketplace.
