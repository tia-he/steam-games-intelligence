# Phase 1 — Data Audit & Feasibility

Snapshot date referenced throughout: **2026-08-28**. All "current" fields are as-of this data pull, not as-of each game's launch date.

## Dataset Snapshot

| File | Rows | Columns | File size | In-memory (deep) |
|---|---|---|---|---|
| `steam_games.csv` | 139,076 | 42 | 917.1 MB | ~938 MB |
| `steam_games_reviews.csv` | 13,039 | 3 | 4.8 MB | ~5 MB |

Both files load comfortably in a single pass on an 8 GB machine (~13s load time for the games file); no chunking was required.

## Main Game Data Findings

- `app_id` is unique in both files (0 duplicates) — confirmed as the correct join key. `name` is **not** safe as a key: 137,664 unique names across 139,076 rows (1,411 duplicated names).
- 0 fully-duplicate rows. `release_date` parses for 138,993/139,076 rows (83 failures); parsed range is 1997-06-30 to 2026-08-25, no invalid/future dates beyond the snapshot date.
- `steam_spy_available` is **constant** (`True` for all 139,076 rows) — no discriminative value in this snapshot. `steam_store_available` is `True` for all but 15 rows.
- Catalog growth is extreme: releases climb from single/double digits per year before 2010 to 24,687 games in 2025 and 17,027 already in the partial 2026. **2024–2026 alone account for ~44% of the entire catalog.**
- `price` has heavy right-skew (mean $9.03 vs median $4.99) driven by genuine outliers, e.g. two titles priced at $107,500. `price_status` is mostly consistent with `price == 0` for "free," but 668 "free" rows carry a nonzero price and 3,374 "unavailable" rows carry a nonzero price (stale pricing on delisted/changed listings).
- **Schema inconsistency discovered:** `genres` and `categories` are serialized in two different formats within the same column — a plain string list (`["Action","Adventure"]`, ~101k rows) and a raw Steam-API dict list (`[{"id":"4","description":"Casual"}]`, ~29.5k rows). This dict-list subset is (almost) exactly the same set of rows where `estimated_owners` uses a different delimiter convention (`"0 .. 20,000"` vs `"0 - 20000"`). This strongly suggests the file is a **merge of at least two differently-formatted source extracts** that was never fully normalized — a general caution for trusting any single field's format uniformly.

## Review Data Findings — major deviation from documentation

**The `reviews` field does not contain JSON, and does not contain up to ~100 Steam user reviews per game, as the source documentation claims.** Empirical inspection shows:

- Empty games are encoded as the literal string `"[]"` (594/13,039 = 4.56%). Non-empty games contain a **plain concatenated text blob**, not structured JSON: `"“quote text” score/rating – outlet"`, repeated 0–10 times with no delimiter between entries.
- This is the Steam store page's **curated critic/press pull-quote carousel** (e.g. *"'Mind Labyrinth VR Dreams Gets Emotional' — VR The Gamers"*), not the community user-review system. Confirmed by: zero occurrences of `voted_up` or `recommendationid` (the actual Steam user-review API fields) anywhere in the file, and only 1 occurrence of "hrs on record" phrasing across the entire dataset.
- Quotes per game: mean 2.30, median 3, **max 10** (not ~100). Quote text length: mean 124 chars, median 100 (short pull-quotes, not full reviews).
- **No per-review structured fields exist at all**: no rating flag, no timestamp, no playtime, no helpfulness votes, no user identifier, no purchase info. Only free text + a trailing attribution string.
- 28,654 total quotes across 12,445 games with content; 10,553 distinct outlet strings recognized (PC Gamer, Rock Paper Shotgun, IGN, Destructoid, Kotaku, Eurogamer among the most frequent), plus smaller blogs, YouTube channels, and some player/itch.io quotes mixed in.

This is the single biggest finding of Phase 1 and materially changes the "Review Intelligence / NLP" module (see below).

## Join Coverage

| Metric | Value |
|---|---|
| Unique `app_id` in games | 139,076 |
| Unique `app_id` in reviews | 13,039 |
| Matched | 13,039 |
| Games-only | 126,037 |
| Reviews-only | 0 |
| Match % of games | **9.38%** |
| Match % of reviews | 100.0% |
| Name mismatch on matched IDs | 0 (0.00%) |

Cardinality is clean 1:1 and every reviews-file ID resolves into the games file with an exact name match — the join itself is trustworthy. The limitation is coverage, not correctness: only 9.4% of the catalog has any press-quote entry at all.

## Data Quality Issues

- Dual serialization formats for `genres`/`categories`/`estimated_owners` (see above) — must be normalized before use; handled in `src/audit_utils.py::parse_list_field` / `parse_estimated_owners`.
- `estimated_owners` is extremely coarse: only 27 unique bucket values across the whole catalog, and roughly 82% of all games fall into just the bottom one or two buckets (`"0-0"` or `"0-20000"` equivalents).
- `metacritic_score` is 26.8% missing, and among non-missing values the median is 0 — the column mixes "truly absent" with "present but unscored," so raw use will bias any statistic toward zero.
- `user_score` is populated for 100% of rows but >99% of values are 0 — the field appears effectively unpopulated/deprecated in this snapshot and has low standalone usability.
- `average_playtime_forever` is 91.4% zero and `median_playtime_forever` is 0 in essentially every release-year cohort — very weak signal regardless of leakage concerns.
- `recommendations` is 84.1% zero-inflated among non-missing values, plus 21.9% missing outright.

## Review Coverage / Sampling Bias

Games with a press-quote entry differ systematically from those without:

| | Has review entry (n=12,445) | No review entry (n=126,631) |
|---|---|---|
| Median release year | 2020 | 2023 |
| Median price | $9.99 | $3.99 |
| % free | 8.9% | 21.0% |
| Median total user-reported reviews (`positive+negative`) | 107 | 2 |

Genre mix also shifts: covered games over-index on Adventure (16.7% vs 13.1%), Strategy, and RPG, and under-index on Free To Play (2.1% vs 4.0%), Early Access (1.7% vs 3.6%), and Casual (11.7% vs 15.8%).

**Implication:** press-quote coverage is a proxy for "got noticed by games media," not a random sample of the catalog. Any conclusion drawn from this text data describes *press-covered, typically older, paid, more narrative-genre titles* — it should not be generalized to the Steam catalog as a whole, and should never be described as player-sentiment analysis, since no player review text exists in this dataset. Additionally, **review sampling mechanism for the (non-existent) player-review use case is formally unknown**; for the critic-quote content that does exist, the "mechanism" is Steam's own promotional curation, which is itself a biased, self-selecting sample by construction.

## Temporal & Leakage Risks

Nearly every candidate outcome variable (`estimated_owners`, `positive`, `negative`, `recommendations`, `peak_ccu`, `average_playtime_forever`, `dlc_count`) is a **current cumulative value**, not a value observed at launch. `price` and `price_status` are current-snapshot and cannot be assumed equal to launch price. `steam_store_available` reflects present-day listing status, not launch-time status.

The exposure-time confound is severe and directly visible in the data: naive Pearson correlation between game age and outcomes looks weak (0.02–0.05) because it's diluted by the huge, near-zero-variance mass of very recent releases, but the release-year-stratified medians tell a different story — median total reviews rises from near 0 for 2025–2026 releases to >1,000 for 2011–2013 cohorts, then declines again for the oldest, smallest-sample cohorts. See `figures/phase1/05_outcome_vs_release_year_exposure_time.png`. **Any model trained on the full catalog using current-cumulative targets will substantially learn "how long has this game been listed," not "was this game successful."**

`achievements` and `dlc_count` are also not safely launch-known: achievement counts can be patched in later, and `dlc_count` grows by definition after launch as DLC ships.

## Candidate Success Outcomes

Inspected (not chosen as a target): `positive`, `negative`, `recommendations`, `peak_ccu`, `estimated_owners` (midpoint), `average_playtime_forever`.

- `positive`, `negative`, `recommendations`, `peak_ccu`, and owners-midpoint are strongly inter-correlated (r = 0.72–0.99), i.e. largely redundant measures of one underlying "popularity" factor.
- `average_playtime_forever` is nearly uncorrelated with `positive` (r = 0.014) and is 91% zero — a weak, likely unreliable signal on its own.
- All are heavily right-skewed and zero-inflated; log-transforms or hurdle-style treatment would be needed before any modeling.
- No threshold (e.g. top 10%/20%) was chosen in this phase, per scope.

## Module Feasibility

| Module | Status | Evidence | Main Risk | Recommendation |
|---|---|---|---|---|
| Steam Market Analytics | **GO** | Full 139K-row catalog; clean genre/category/tag/price/platform/developer/publisher fields once normalized. | `estimated_owners` extremely coarse (27 buckets, ~82% in bottom bucket); price is current, not launch, price. | Frame around catalog structure, pricing, genre/tag landscape, platform trends — descriptive, not owner-volume-precise. |
| Review Intelligence / NLP | **MODIFY** (scope-down) | Only 28,654 short critic/press quotes (median 3/game, ~124 chars) covering 9.4% of the catalog; zero per-review structure. | Documented "up to 100 player reviews" schema does not exist; not player-voice data; strong coverage-selection bias toward older, pricier, press-visible titles. | Rename to a small "Critical Reception Signal" module: outlet-coverage counts, quote presence as a feature, light text stats. Drop plans for large-scale topic modeling / aspect sentiment / player-voice NLP — the corpus can't support it. |
| Game Success Modeling | **MODIFY** (hard constraints) | Rich metadata + popularity fields exist, but every outcome candidate is a current cumulative snapshot with a demonstrated severe exposure-time confound. | Prospective "predict success at launch" is **not defensible** with this dataset — there is no at-launch snapshot, only one current cross-section. | Reframe as *correlational description of current standing conditioned on exposure time* (e.g., outcomes-per-month-since-release, or a fixed age-matched cohort), not prediction. Defer target definition and thresholds to Phase 2 with these constraints explicit. |
| Content-Based Game Similarity / Recommendation | **GO** (content-based only) | Genres, categories, tags (451 unique), descriptions, developer/publisher all usable after normalization. | No user-game interaction data anywhere in either file — collaborative filtering is categorically out of scope. Tags missing for 40% of games. | Build pure content-based similarity (metadata + description-text embeddings). Explicitly label the module "content-based," never "recommendation via collaborative filtering." |

## Recommended Changes to Project Roadmap

1. **Rewrite the Review Intelligence module's premise.** It cannot be a player-review NLP module as originally scoped — the data is critic/press pull-quotes, not user reviews, at a much smaller scale (28.6k short quotes, not "up to 100 reviews × 139k games").
2. **Do not build a "predict game success at launch" model.** Reframe Success Modeling around current standing conditioned on exposure time, or restrict to a fixed age cohort with explicit caveats; treat this as a stretch module pending Phase 2 design, not a committed deliverable.
3. **Normalize schema before any further work**: two mixed serialization formats for `genres`/`categories`/`estimated_owners` must be reconciled (parsers already written in `src/audit_utils.py`).
4. **Keep Market Analytics and Content-Based Similarity as the strongest, best-supported modules** — build the portfolio narrative around these first, with Success Modeling and Critical Reception as clearly-scoped, appropriately caveated secondary modules.

## Open Questions for Phase 2+

- Is a historical/time-series snapshot of any field obtainable (e.g. a second data pull weeks/months apart) to escape the single-cross-section limitation for success modeling?
- What explains the two mixed source formats in `steam_games.csv` — two scrape dates, two upstream APIs? Does the dict-list/dotdot subset (~29.5k rows) differ in reliability from the rest?
- Should `estimated_owners` be dropped in favor of `positive`/`negative`/`recommendations` as a continuous popularity proxy, given its extreme bucket coarseness?
- Is there any way to distinguish genuine critic outlets from player/community quotes within the `reviews` field's attribution strings, to build a cleaner "professional press only" subset?
- Given `steam_spy_available` is constant in this snapshot, was the raw source dataset pre-filtered to SteamSpy-available titles only, and does that itself introduce catalog-coverage bias worth documenting?
