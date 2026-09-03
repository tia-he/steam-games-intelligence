# Phase 6 — Similar-Game Peer Benchmarking & Portfolio Synthesis

Full code, evidence, and figures: `notebooks/06_peer_benchmarking_and_synthesis.ipynb`, `figures/phase6/`,
`outputs/phase6_peer_benchmarks.csv`, `outputs/phase6_case_studies.csv`, `outputs/phase6_segment_table.csv`,
`src/peer_benchmark_utils.py`.

## Research Question

Among content-similar Steam games, which titles attract unusually high or low visibility relative to
comparable peers? This is a **descriptive peer-benchmarking** exercise — not causal inference, not another
success-prediction model, not a personalized recommender, and not an explanation of *why* games succeed.

## Why Peer Benchmarking

Phases 1-5 built two independent, non-causal analytical lenses on the same catalog: Phase 4's leakage-controlled
model of cohort-relative visibility, and Phase 5's content-based similarity representations. Neither phase asked
what happens when the two are combined. Phase 5's own closing recommendation named this exact next step:
comparing each game's observed visibility against its content-similar peer set, "a natural extension that stays
within this project's established non-causal, cohort-aware methodology." Phase 6 executes that extension and
closes out the project's substantive analytical work.

## Population

Phase 5's similarity population and Phase 3/4's modeling population were built independently for different
purposes and do not fully overlap:

| Population | n | Basis |
|---|---|---|
| Phase 5 similarity population | 129,847 | Any release year; excludes only missing names, pure creative/productivity software, demo listings, and rows with no content at all |
| Phase 3/4 modeling population | 67,241 | 2017-2023 releases only (pre-2017 = different marketplace regime; 2024-2026 = insufficient review-accumulation time) |
| **Phase 6 overlap (used)** | **63,598** | Inner join on `app_id` |
| Excluded from Phase 5 pop | 66,249 | Released outside 2017-2023 (pre-2017 or 2024-2026) — no valid cohort-relative visibility percentile exists for these |
| Excluded from Phase 3/4 pop | 3,643 | 2017-2023 releases that Phase 5 excluded for content reasons (missing name, creative-software listing, demo listing, or literally no genre/category/tag/description content) |

Peer benchmarking needs **both** a valid Phase 5 content representation and a valid Phase 3/4 cohort-relative
visibility percentile for every game used as a query or as a peer, so the 63,598-game overlap is used
exclusively — for both queries and candidate peers — rather than silently mixing the two populations. This
covers 94.6% of the Phase 3/4 modeling population and 49.0% of the Phase 5 similarity population.

## Peer Definition

Peers are selected using **content similarity only** — the Phase 5 hybrid representation (structured
metadata + semantic description embeddings, `alpha=0.5`, Phase 5's recommended default, re-affirmed here as an
interpretable default, not an empirically "optimal" weight). No popularity/outcome field — `total_reviews`,
`positive_ratio`, `estimated_owners`, `recommendations`, `peak_ccu`, playtime, or the Phase 4 prediction score —
is ever used to choose a peer; visibility is looked up only *after* the peer set is fixed. The structured
representation is rebuilt cheaply from cached list columns; the semantic embeddings are the **cached Phase 5
matrix**, loaded from disk and never recomputed (Phase 5 spent ~22 minutes of CPU time producing them once).

**Franchise/duplicate suppression:** Phase 5 documented strong franchise/edition effects (a game's nearest
"neighbor" can be its own remaster). `src/peer_benchmark_utils.py::franchise_key` is a vectorized version of
Phase 5's `is_likely_same_franchise` heuristic (same first-significant-title-word rule), applied per game so
franchise suppression scales to tens of thousands of candidates per query instead of a pairwise Python loop.
Documented as a lightweight heuristic, not full entity resolution — it will both under- and over-trigger, same
as the Phase 5 original. Exact-duplicate names are also excluded.

**K sensitivity:** one batched retrieval computes the top-50 content peers for every game in the population
(dense matmul in batches; ~2.2 minutes total for 63,598 x 63,598 candidate pairs); K=10/20/50 benchmarks are
all derived from this single top-50 list, so no extra retrieval is needed per K. K=20 is used as primary
throughout this report — a reasonable middle ground, not an untested default (see Robustness below).

**Comparing suppressed vs. raw:** on a 4,000-game sample, franchise-suppressed and raw (unsuppressed) peer
sets produce nearly identical peer-relative-gap rankings at the population level (Spearman rho = 0.994) — the
suppression barely changes the *aggregate* picture. It matters at the individual-game level, though: without
it, a query's top peer is very often its own sequel/edition, which makes any single peer comparison close to
trivial. **Decision: franchise-suppressed peers are the primary mode**, for the interpretability of individual
comparisons, not because the aggregate benchmark depends on it.

## Visibility Measure

**Phase 3's cohort-relative visibility percentile** (`target_pct_within_cohort` in `modeling_frame.parquet`)
is reused unchanged — never raw `total_reviews`, which Phase 3 showed is severely exposure-time confounded
(raw rho vs. game age = 0.569; release-year-percentile rho vs. age = 0.011). Content similarity alone does not
guarantee temporal comparability (a 2017 game and a 2023 game can be highly content-similar but have
incomparable raw review counts), which is exactly the problem the cohort-relative percentile already solves —
each peer's visibility is read off relative to *its own* release-year cohort, not the focal game's.

**Was additional temporal restriction of peer selection necessary?** Tested directly: restricting each
query's candidate peers to release years within ±1 or ±2 years, vs. the unrestricted (any release year)
design, on the same 4,000-game sample. Both restricted variants agree closely with the unrestricted design
(Spearman rho = 0.912 at ±1yr, 0.948 at ±2yr) — since visibility is already cohort-percentile normalized, a
further temporal window on peer *selection* changes conclusions only modestly. **Decision: keep the simpler
any-year design as primary** — cohort normalization already does most of the work, and the added complexity
of a temporal window is not clearly justified by the small stability gain it buys.

## Peer-Relative Visibility Gap

For each game *i* with K content peers:

```
peer_visibility_median  =  median(peer visibility percentiles)
peer_visibility_gap     =  focal visibility percentile  −  peer_visibility_median
```

**Median, not mean**, is used for the peer center: peer-set visibility percentiles are not symmetric within a
given peer set (a handful of unusually high- or low-visibility peers, common given the long tail, would
otherwise dominate a mean), so the median is the more robust choice.

This is a strictly **descriptive** quantity. A positive gap means *this game has higher observed visibility
than its content-similar peer set*; a negative gap means the opposite. It is **not** called excess success,
causal uplift, a residual, alpha, or unexplained performance anywhere in this project — the preferred term
throughout is **peer-relative visibility gap**.

## Robustness to K and Representation

Spearman rank correlations of `peer_visibility_gap` across eight specifications (K=10/20/50 on the full
63,598-game population; franchise-suppression, representation, and temporal-window comparisons on a 4,000-game
sample, all against the full corpus):

| Comparison | Spearman rho |
|---|---|
| K=10 vs. K=20 | 0.947 |
| K=20 vs. K=50 | 0.961 |
| K=10 vs. K=50 | 0.918 |
| Franchise-suppressed vs. raw (K=20) | 0.994 |
| Hybrid vs. structured-only (K=20) | 0.839 |
| Hybrid vs. semantic-only (K=20) | 0.800 |
| Structured-only vs. semantic-only (K=20) | 0.676 |
| Any-year vs. peers within ±1yr | 0.912 |
| Any-year vs. peers within ±2yr | 0.948 |

**Reading this table:** K choice, franchise handling, and temporal restriction all leave the broad ranking of
peer-relative gaps essentially intact (rho ≥ 0.91 throughout). Representation choice moves the ranking the
most — structured-only and semantic-only agree only moderately (rho = 0.676) — which is the *expected* result
given Phase 5's finding that structured and semantic similarity scores are themselves weakly *negatively*
correlated (Pearson r = -0.27) on the same candidates: they capture genuinely different notions of
"similar." **Conclusion: broad peer-relative-visibility conclusions are robust to K and to franchise/temporal
design choices; they are moderately, honestly, representation-dependent — this is reported as a real
limitation, not hidden by picking whichever specification looks most interesting.**

## Peer-Set Quality

Not every game has an equally coherent peer set. Peer-set quality is measured as mean/median/min Top-20
similarity and similarity spread (max − min among the K peers). Quality tiers were built from the observed
distribution's quartiles (25th/75th percentile of mean Top-20 similarity: 0.548 / 0.625) rather than an
invented cutoff:

| Tier | n | Mean-similarity range | Median gap | Std. dev. of gap |
|---|---|---|---|---|
| Weak peer match | 15,900 | bottom quartile (< 0.548) | -0.071 | 0.256 |
| Moderate peer match | 31,798 | middle 50% | +0.023 | 0.212 |
| Strong peer match | 15,900 | top quartile (> 0.625) | +0.009 | 0.193 |

Gap variability falls monotonically as peer-set quality rises (weak → moderate → strong: std. dev. 0.256 →
0.212 → 0.193), and games with weak peer sets skew toward negative gaps in aggregate. The correlation between
mean peer similarity and |gap| is modest but consistently negative (Spearman rho = -0.163) across the full
population. **Weak peer sets should be read with more caution, not overinterpreted as unusual performance** —
they are used as a quality-control filter for the curated examples and case studies below, not discarded from
the underlying data.

## Distributional Findings

`peer_visibility_gap` (K=20, hybrid, franchise-suppressed), n = 63,598:

| Statistic | Value |
|---|---|
| Median | 0.000 |
| IQR | [-0.159, 0.140] |
| 5th / 95th percentile | -0.404 / 0.339 |
| 1st / 99th percentile | -0.567 / 0.467 |
| Min / Max | -0.848 / 0.812 |

The distribution centers essentially at zero, which is expected for a relative benchmark computed from
overlapping peer neighborhoods (most games are, on average, similar in visibility to their own content
neighborhood), with a long, roughly comparable-magnitude tail in both directions. See
`figures/phase6/02_gap_distribution.png`.

## Higher-Visibility Relative to Similar Peers

Quality-controlled (moderate/strong peer match only; obvious duplicate-listing artifacts and adult-content
titles excluded from the curated *figure*, though not from the underlying CSV) examples with the largest
positive `peer_visibility_gap`: **Pretty Angel**, **Defiance 2050 - Beta**, **True Puzzle**, **Orb of
Creation**, **Nyasha**, **BOMJMAN** — all niche, largely-unfamiliar titles whose content peers (by shared
genre/category signature) are themselves overwhelmingly obscure, so a moderate absolute visibility already
reads as a large *relative* outperformance of that neighborhood. See `figures/phase6/05_higher_lower_examples.png`
and the fuller (unfiltered) list in `outputs/phase6_peer_benchmarks.csv`.

## Lower-Visibility Relative to Similar Peers

The largest negative `peer_visibility_gap` examples include **FFXV WINDOWS EDITION 4K Resolution Pack**,
**Shn!p**, **Zup! Q**, **Battle Teams 2**, **4x4 Offroad Racing - Nitro**. The FFXV case is the most
observably interesting: it is a Square Enix-published resolution-pack listing whose closest content peers (by
shared `RPG` genre and multiplayer categories) are mainline `FINAL FANTASY` titles — extremely high-visibility
games in their own right. A technical add-on listing structurally cannot accumulate comparable review counts
to a full standalone release, which is an observable, descriptive difference — not a claim about *why* the
gap exists causally.

## Case Studies

Five cases (`outputs/phase6_case_studies.csv`), deliberately not all famous and not all clean:

1. **HighFleet** (2021, indie strategy/action) — visibility percentile 0.984, peer median (K=20) 0.318,
   **gap = +0.666**, mean peer similarity 0.624 (moderate). Content peers (`Invention 4`, `Space Squadron`,
   `Meteor Shower`, `Survival Night`, `Captain vs Sky Pirates`) share the `Action/Adventure/Indie/Strategy`
   genre signature but sit far lower in their own cohorts. See `figures/phase6/06_case_study_highfleet.png`.
2. **One Finger Death Punch 2** (2019, indie action/casual) — visibility percentile 0.969, peer median 0.309,
   **gap = +0.661**, mean peer similarity 0.592 (moderate). Peers (`Bully Beatdown`, `One Hit KO`, `Color
   Slayer`, `抵御者 Defender`, `Beatdown Brawler`) share genre and Steam Achievements/Cloud/Leaderboards
   categories.
3. **FFXV WINDOWS EDITION 4K Resolution Pack** (2018, Square Enix) — visibility percentile 0.119, peer
   median 0.967, **gap = -0.848**, mean peer similarity 0.582 (moderate). Peers are mainline `FINAL FANTASY`
   titles sharing the `RPG` genre and multiplayer categories — an add-on/utility listing benchmarked against
   full releases of the same franchise family.
4. **MX vs ATV All Out** (2018, THQ Nordic) — visibility percentile 0.944, peer median 0.936, **gap = +0.008**,
   mean peer similarity 0.652 (**strong**). Peers (`MX vs ATV Legends`, three `MXGP` titles) are a tight,
   coherent motocross/racing-sim cluster — the cleanest example of a well-behaved, near-zero benchmark.
5. **Getting Over It with Bennett Foddy** (2017, first-time developer) — visibility percentile 0.995, peer
   median 0.409, nominal **gap = +0.587**, but mean peer similarity only **0.503 (weak peer match)**. This is
   the flagged ambiguous case: a famous, extremely visible game whose best available content peers (`The
   Legend of the Dragonflame High School`, `3, 2, 1, SURVIVE!`, `Punch It Deluxe`, and others sharing only
   the broad `Action` genre) are not a coherent neighborhood — the game's distinctive "rage-platformer"
   identity is not well captured by the available structured/semantic signal. **The large nominal gap here
   should not be read as a genuine finding** — it is a direct illustration of why the peer-quality tier exists.

## Segment-Level Findings

(`outputs/phase6_segment_table.csv`, medians/means of `peer_visibility_gap_k20`)

| Segment | n | Median gap | Mean gap |
|---|---|---|---|
| Indie | 46,015 | +0.003 | -0.008 |
| Non-Indie | 17,583 | -0.006 | -0.028 |
| Free To Play | 10,377 | -0.020 | -0.064 |
| Paid | 53,221 | +0.005 | -0.003 |
| First-time developer | 37,153 | -0.020 | -0.031 |
| Experienced developer | 26,445 | +0.023 | +0.011 |

Free To Play titles and first-time-developer titles both skew toward negative peer-relative gaps; experienced
developers skew positive. This is directionally consistent with — though a distinct finding from — Phase 4's
error-analysis observation that first-time-developer/budget-indie titles are the model's characteristic blind
spot. Release-year segments show no dramatic breakdown (all medians within ±0.035 of zero), with 2020 the
single most negative cohort (median -0.035) — plausibly a catalog-supply-surge artifact from that year, not
investigated further here. No segment difference is interpreted causally.

## Connection to Phase 4

The frozen Phase 4 conservative LightGBM model (exact spec reproduced from `outputs/phase4_modeling_results.md`
— same 90 features, same hyperparameters, `num_boost_round=268`, trained on 2017-2021 only) was reproduced to
get predicted visibility probabilities for the Phase 6 population. This is a faithful reproduction, **not**
retuning or reopened model selection: validation ROC-AUC/PR-AUC reproduced at 0.810/0.576 (frozen spec:
0.811/0.577) and test at 0.800/0.554 (frozen spec: 0.801/0.553) — small differences consistent with expected
floating-point/library-version reproduction noise.

- rho(actual cohort-relative visibility, Phase 4 predicted probability) = **0.467**
- rho(peer-relative visibility gap, Phase 4 predicted probability) = **0.172**

The peer-relative gap correlates only weakly with the Phase 4 metadata classifier's output, while both
correlate more strongly with actual visibility itself — **peer-relative benchmarking surfaces a largely
different signal than the leakage-controlled metadata model, not a redundant one.** Filtering for actual
visibility percentile > 0.8, Phase 4 predicted-probability rank < 0.3, and peer-relative gap > 0.2 surfaces
roughly 500 "metadata-unexpected high-visibility" titles — simultaneously high actual visibility, low
metadata-predicted probability, and much higher visibility than their content peers. This is an interesting
intersection of two independently-built parts of this project, but **not** evidence of an "unexplained cause":
neither lens can say *why* these specific games attracted attention, only that both descriptive lenses flag
them as unusual by different criteria.

## Connection to Phase 5 Long-Tail Discovery

Phase 5 found that content retrieval is systematically biased *toward* less-visible games, not more-visible
ones, because the catalog itself is long-tail dominated. Peer benchmarking reproduces and sharpens this inside
narrow content niches: rho(focal visibility percentile, peer median percentile) = 0.597 — a real but far from
1:1 relationship. Grouping focal games into visibility deciles, the top decile (focal mean ≈ 0.95) has content
peers whose median visibility averages only ≈ 0.75, and the bottom decile (focal mean ≈ 0.11) has peers
averaging ≈ 0.38 — both ends pulled toward the middle of the local content-neighborhood's visibility
distribution. **Even the most visible games in a content niche are typically surrounded by dozens of far less
visible, genuinely content-similar peers** — Steam's long tail reappears *inside* narrow content clusters, not
only across the catalog as a whole. This is the project's clearest new synthesis finding, and a direct,
supported extension of Phase 5's original popularity-bias observation rather than a forced one. See
`figures/phase6/07_long_tail_connection.png`.

## What This Analysis Can Tell Us

- Which Steam titles have notably higher or lower cohort-relative visibility than a defensible,
  content-only-selected set of comparable peers, and how confidently (via peer-set quality).
- That this relationship is broadly robust to reasonable design choices (K, franchise handling, temporal
  window) and moderately representation-dependent.
- A concrete, quantified extension of Phase 5's long-tail finding: extreme visibility disparities exist even
  within narrow, genuinely content-similar clusters.
- A complementary (not redundant) signal to Phase 4's leakage-controlled metadata model.

## What It Cannot Tell Us

- **Why** any specific game over- or under-performs its peers — no causal mechanism is identified or implied.
- Whether a game is objectively "better" or "worse" than its peers — the benchmark is visibility, not quality,
  revenue, or player satisfaction.
- A trustworthy signal for games with weak peer sets — flagged, not corrected.
- Anything about games outside the 2017-2023 Phase 3/4 population, or about a catalog whose composition has
  shifted materially since this snapshot (2026-08-28).
- A personalized recommendation — peers are content-similar by construction, never preference-similar.

## Final Project-Level Insight

Combining Phases 4 and 5 does not produce a stronger predictive claim — it produces a more precise
*descriptive* one. The single most portfolio-worthy Phase 6 finding is that Steam's long-tail structure, which
Phase 2 first documented at the catalog level and Phase 5 rediscovered as a retrieval characteristic,
reappears at the narrowest possible resolution: inside individual games' own closest content neighborhoods.
No amount of genre/tag/description similarity implies comparable visibility — a methodologically disciplined
way of saying that content resemblance and market attention are, empirically, mostly separate axes on this
platform.
