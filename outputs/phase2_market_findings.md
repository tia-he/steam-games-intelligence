# Phase 2 — Steam Market Analytics

Snapshot date: **2026-08-28**. All findings describe the current state of the Steam catalog (`steam_games.csv`,
139,076 games) unless a figure explicitly compares release cohorts. Full methodology, code, and figures:
`notebooks/02_market_analytics.ipynb`, `figures/phase2/`.

**Scope note:** this is descriptive market analytics. No predictive model, success-label definition, or
NLP/embeddings/clustering/recommendation work is included — see `outputs/feasibility_summary.md` for why
those remain out of scope until later phases.

## 1. Marketplace Evolution

- **Finding:** Catalog growth was not broad-based. Between the 2014-2016 and 2023-2025 release cohorts, the
  whole catalog grew ~7.2x, but Free To Play releases grew ~14.3x and Early Access ~10.3x — both far
  outpacing the catalog — while Action (~5.8x) and Strategy (~6.4x) grew the slowest among major genres.
  The free ($0) share of new releases rose from 3.5% (2010) to ~26% (2024-2025).
- **Evidence:** `figures/phase2/fig1_release_volume_by_year.png`, `fig2_free_to_play_share_by_year.png`,
  `fig3_genre_prevalence_trends.png`.
- **Interpretation:** Steam's growth is better described as a *compositional shift* toward free-to-access and
  early-access release models than as uniform expansion of the same kind of catalog. Action's and Strategy's
  *share* of releases declined even as their absolute counts kept growing. 2026 is a partial year (17,027
  releases through 2026-08-28, ~69% of 2025's full-year total already) and is explicitly excluded from
  year-over-year comparisons that would otherwise treat it as a completed year.

## 2. Market Crowding & Concentration

- **Finding:** Genre landscape (multi-label prevalence, not mutually exclusive shares): Indie 66.5%, Casual
  41.8%, Action 37.3%, Adventure 36.3% of the catalog. Free To Play and Early Access are the fastest-growing
  segments in recent cohorts. Developer/publisher supply is extremely fragmented: 86,963 unique developers
  and 73,219 unique publishers, with **~77% of each appearing in exactly one catalog record**. The top-10
  developers combined hold only **1.1%** of all developer-game links (HHI ≈ 0.6 out of 10,000).
- **Evidence:** `figures/phase2/fig4_genre_landscape_prevalence_and_growth.png`,
  `fig5_developer_catalog_concentration.png`.
- **Interpretation:** Steam's catalog is **not** dominated by a small number of publishers/developers on a
  release-count basis — supply is a long tail of mostly one-off producers. This is a *catalog/release*
  concentration statement, not a revenue or economic-market-share one (the dataset has no sales/revenue
  field, and a single blockbuster from a major publisher can matter commercially far more than its 1-of-many
  catalog count suggests).

## 3. Pricing Structure

- **Finding:** Current prices cluster tightly around recognizable Steam price points (median paid price
  $5.99; 90th percentile $19.99). The extreme prices Phase 1 flagged (up to $107,500) are explainable, not
  data errors: a mix of deliberate novelty/shock listings (e.g. a game literally titled and described as "the
  most expensive game on Steam") and legitimate professional creative-software titles sold through the game
  storefront (e.g. Houdini Indie $299, VEGAS Edit 20 $249). Median *current* paid price is higher for older
  release cohorts (~$9.99 for 2010-2013) than recent ones (~$4.99 from 2017 on).
- **Evidence:** `figures/phase2/fig6_price_distribution_paid_games.png`, `fig7_price_by_genre.png`,
  `fig8_price_by_release_cohort.png`.
- **Interpretation:** All prices discussed are **current** price, not launch price, which does not exist in
  this dataset. The cohort-price pattern is genuinely ambiguous with the data available: it is consistent
  with older paid titles receiving permanent price cuts over their much longer time on the storefront, and
  equally consistent with newer cohorts skewing toward budget/indie titles from the start (matching the
  Casual/Indie-prevalence rise found in Question 1). The data cannot separate these two explanations without
  launch-price history, which this snapshot does not contain.

## 4. Player Reception & Popularity

- **Finding:** `total_reviews` (positive+negative) and a review-count-gated `positive_ratio` are the only
  outcome metrics reliable enough to use — `average_playtime_forever` (91.4% zero), `recommendations` (62%
  zero of non-missing, plus 21.9% missing), and `peak_ccu` (85.8% zero) were evaluated and excluded as too
  weak/sparse. A minimum of 10 reviews was used for all positive-ratio comparisons (below this, the ratio's
  standard deviation is still shrinking sharply: 0.239 at 1 review vs. 0.179 at 10). Even with these metrics,
  40.3% of the entire catalog has zero recorded reviews and 59.2% has fewer than 10.
- **Evidence:** `figures/phase2/fig9_review_volume_long_tail.png`,
  `fig10_genre_reception_alltime_vs_recent_cohort.png`, `fig11_positive_ratio_by_price_tier.png`.
- **Interpretation:** The clearest finding is a genuine exposure-time confound, directly visible when
  controlling for release cohort: **Massively Multiplayer has the highest all-time median total_reviews (17)
  of any major genre, but the 2023-2024 release cohort's MMO median collapses to 1 — the lowest of any
  genre shown** (see below). Positive-review ratio shows a mild, non-monotonic "sweet spot" around the
  $10-19.99 price tier (median 83.3%) rather than rising steadily with price — Free and $40+ both sit lower
  (~78-79%).

## Cross-Cutting Insights

- The same structural shift shows up from two directions: Question 1's rising free-to-play/Early-Access share
  and Question 2's fastest-growing-genre ranking both point to the same change in *how* games are being
  brought to market, not just how many.
- The pricing "sweet spot" (Question 3/4) and the fragmented-supply finding (Question 2) together suggest a
  catalog where most producers are small, one-off, and priced in a narrow low-to-mid band — there is little
  evidence of either a small dominant-publisher cohort or a strong price-reception relationship that a
  concentrated market might otherwise produce.
- Long-tail visibility (Question 4: 40.3% zero reviews) is consistent with, and reinforces, Phase 1's finding
  that `estimated_owners` is bottom-heavy (~82% of the catalog in its lowest one or two buckets) — both
  independently point to most Steam games receiving very little observable player attention.

## Implications for Later Phases

- Any success-modeling or similarity work in later phases should treat release cohort as a required control,
  not an optional one — Question 4 shows an all-time genre ranking can fully invert once cohort is held
  constant.
- `total_reviews` (with a minimum-count gate) and cohort-relative positioning are more defensible outcome
  signals than raw `estimated_owners` or single-genre-only comparisons.
- The fragmented developer/publisher structure means developer/publisher identity is unlikely to be a strong
  standalone predictive feature (no small set of studios drives the catalog) — genre, price tier, and cohort
  timing look like more promising structured features than producer identity alone.

## Limitations

- This is a current snapshot, not a historical census — games delisted before the snapshot are invisible, so
  very old cohorts may be undercounted relative to their true historical size.
- `estimated_owners` (27 coarse buckets) was not used as a primary outcome in Question 4; `total_reviews` and
  `positive_ratio` were judged more usable, but neither is a precise ownership or satisfaction measure.
- Genre/category prevalence figures are multi-label and can sum above 100% within a year or cohort — they are
  never mutually-exclusive market shares.
- Developer/publisher concentration is measured by catalog/release count only; this dataset has no
  revenue/sales field, so no economic-market-share claim is made or supported.
- All comparisons are descriptive associations within the current snapshot; none of the findings above are
  causal claims.
