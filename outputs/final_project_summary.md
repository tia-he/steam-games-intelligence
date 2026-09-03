# Final Project Summary — Steam Games Intelligence

A technical synthesis of the full six-phase project. README.md is the recruiter-facing overview; this
document is the fuller technical account of how the project's scope evolved, what survived scrutiny, and what
was deliberately rejected along the way.

## Original Question

The project began with an intentionally broad guiding question: *what makes a Steam game successful, how do
players/critics respond to games, and what can we learn from similar games?* That framing was treated as a
hypothesis about the data, not a fixed deliverable — the plan from the outset was to audit the dataset first
(Phase 1) and let the findings determine which downstream modules were actually defensible.

## How the Data Audit Changed the Roadmap

Phase 1 found two structural problems that reshaped everything downstream:

1. **The `steam_games_reviews.csv` field does not contain player reviews.** Despite its documented schema
   (up to ~100 structured user reviews per game), it actually contains a small number (median 3, max 10) of
   concatenated critic/press pull-quotes scraped from the store page — no per-review structure, no player
   voice. This eliminated any player-sentiment-analysis or review-NLP module from the roadmap outright; the
   "how do players... respond" half of the original question was never supportable by this dataset.
2. **Every popularity/outcome field is a current cumulative snapshot, not a historical measurement.**
   `estimated_owners`, `positive`/`negative`, `recommendations`, `peak_ccu`, and `average_playtime_forever` all
   measure "how much has accumulated as of 2026-08-28," not a fixed-horizon outcome — older games have simply
   had more time to accumulate. This ruled out any literal "predict success" framing (no pre-launch,
   fixed-horizon target exists in a single-snapshot dataset) and forced every later phase to treat release-date
   exposure time as a first-class confound rather than an afterthought.

Both findings were discovered empirically, from the data itself, not assumed from source documentation — the
project's methodological throughline from Phase 1 onward is: **audit before claiming, and let disconfirming
evidence change the plan.**

## Strongest Findings, By Phase

- **Phase 1 — Data Audit & Feasibility.** The critic-quote/player-review documentation mismatch (above) and
  the current-snapshot/cumulative-outcome structural constraint, both discovered empirically and both binding
  for every later phase.
- **Phase 2 — Steam Market Analytics.** Catalog growth is compositional, not uniform (Free To Play releases
  grew ~14.3x vs. Action's ~5.8x, 2014-16 to 2023-25); supply is highly fragmented (~77% of developers/publishers
  appear in only one catalog record); a genre's all-time popularity ranking can fully invert once release cohort
  is controlled for (Massively Multiplayer: highest all-time median reviews, lowest among 2023-24 releases).
- **Phase 3 — Success Definition & Temporal Framing.** Raw `total_reviews` correlates with game age at
  Spearman rho = 0.569; release-year cohort-percentile normalization reduces this to rho = 0.011. A rolling
  ±90-day window was tested and *rejected* after it introduced a worse, opposite-direction artifact (rho =
  -0.392) from right-censoring near the snapshot date. Popularity and reception were tested and confirmed to
  be distinct, non-combinable constructs (rho = -0.073 raw). No engagement target survives (>90% zero
  playtime). Final scope: a narrowly-defined visibility classification target, 2017-2023 population only.
- **Phase 4 — Cohort-Aware Visibility Modeling.** A leakage-controlled LightGBM (genre/category, platform,
  release timing, point-in-time developer/publisher history, static store metadata — 90 features) reaches
  test (2023) ROC-AUC 0.801 / PR-AUC 0.553, with only modest degradation from 2022 validation — real
  one-year-ahead chronological generalization. A "broader snapshot" model (adding price/achievements/tags)
  reaches validation ROC-AUC ≈ 0.911, but a material share of that gain traces to features that are themselves
  partly downstream of popularity (`Steam Trading Cards` turned out to be a near-pure popularity proxy and was
  dropped outright) — the lower-scoring conservative model was selected as the frozen, tested model *because*
  of this finding, not despite it.
- **Phase 5 — Game Representation & Content-Based Similarity.** Structured metadata, TF-IDF text, and
  semantic embeddings (`all-MiniLM-L6-v2`, run locally) were compared, not ranked by an invented metric.
  Structured and semantic similarity scores are weakly *negatively* correlated on the same candidates (Pearson
  r = -0.27), motivating a transparent hybrid as the recommended default rather than a single "best"
  representation. Retrieval is systematically biased *toward* less-visible games (the opposite of the
  hypothesized direction), consistent with the catalog's long-tail composition.
- **Phase 6 — Similar-Game Peer Benchmarking & Portfolio Synthesis.** Combining Phase 4's visibility measure
  with Phase 5's similarity representation on their 63,598-game population overlap, the peer-relative
  visibility gap is broadly robust to K, franchise handling, and temporal restriction (Spearman rho ≥ 0.91),
  moderately representation-dependent (structured vs. semantic: rho = 0.68), and only weakly correlated with
  Phase 4's predicted probability (rho = 0.17) — a genuinely complementary signal. The clearest new synthesis
  finding: Steam's long-tail structure reappears *inside* individual games' own closest content
  neighborhoods, not just across the catalog as a whole.

## Final Defensible Claims

- Steam's catalog supply is extremely fragmented and long-tail dominated, and this shapes every downstream
  measurement (Phase 2).
- Raw cumulative popularity fields are severely confounded by release-date exposure time; cohort-relative
  percentile framing is a validated, evidence-tested correction, not an assumption (Phase 3).
- Observable, leakage-controlled store/catalog metadata carries real, moderate, chronologically-generalizing
  signal about cohort-relative visibility — not commercial success, not quality (Phase 4).
- Steam games can be usefully represented for content-based discovery along complementary structured and
  semantic axes; neither dominates the other (Phase 5).
- Content similarity and observed visibility are largely separate axes: a game's closest content peers are
  frequently far less (or more) visible than itself, robustly across reasonable benchmarking design choices
  (Phase 6).

## Rejected Claims / Methods and Why

- **"Predict whether a game will succeed before launch"** — no fixed-horizon, pre-launch snapshot exists in
  this dataset; rejected at Phase 3.
- **Player-sentiment / review-text NLP** — the reviews file contains critic pull-quotes, not player reviews;
  rejected at Phase 1.
- **A composite success score (popularity × reception)** — tested directly and rejected; the two constructs
  are empirically distinct, and no principled weighting was available (Phase 3).
- **Rolling ±90-day cohort normalization** — tested and rejected after it introduced a worse artifact than
  the raw confound it was meant to fix (Phase 3).
- **The "broader snapshot" Phase 4 model, despite higher validation scores** — rejected as the frozen model
  because a material share of its gain is itself downstream of the popularity it predicts (Phase 4).
- **A single "best" similarity representation** — rejected in favor of reporting complementary strengths;
  structured and semantic scores are weakly negatively correlated, not redundant (Phase 5).
- **Collaborative filtering / personalized recommendation framing** — no interaction, purchase, or rating data
  exists; every similarity claim in Phases 5-6 is content-based discovery, never recommendation accuracy
  (Phase 5).
- **Causal or "unexplained success" framing for Phase 6's peer-relative gap** — deliberately avoided
  throughout; the gap is a descriptive benchmark, and weak-peer-set cases are flagged rather than
  overinterpreted (Phase 6).
- **A new predictive model trained on `peer_visibility_gap`** — explicitly out of scope for Phase 6, to avoid
  reopening a modeling loop this project had already closed at Phase 4.

## Final Limitations

1. Single current snapshot (2026-08-28) — not a historical or panel dataset.
2. Cumulative outcomes cannot support true pre-launch forecasting.
3. Critic pull-quotes are not player-review text; no player-sentiment analysis is possible.
4. Content similarity has no independent user-preference ground truth to validate against.
5. Some current store metadata (price, tags, achievements) is downstream/temporally ambiguous relative to
   launch and was excluded from, or flagged within, the frozen Phase 4 model accordingly.
6. Peer benchmarking (Phase 6) is descriptive, not causal — it identifies *where* visibility diverges from
   content peers, never *why*.

## Portfolio Takeaway

The project's throughline is not any single model or chart — it is that a rigorous, empirical data audit
performed *before* analysis materially changed the roadmap, and every subsequent phase stayed inside the
boundaries that audit established rather than quietly drifting back toward the original, overreaching
question. Two independently-audited outcome fields (a leakage-controlled visibility classifier and a
content-similarity retrieval system) were combined only once both had been individually validated, and even
that combination was scoped as descriptive benchmarking rather than a new predictive claim. That discipline —
audit, scope, test, reject what fails, state plainly what remains — is the actual deliverable.
