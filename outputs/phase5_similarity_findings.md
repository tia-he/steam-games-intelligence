# Phase 5 — Game Representation & Content-Based Similarity

Full code, evidence, and figures: `notebooks/05_game_representation_and_similarity.ipynb`, `figures/phase5/`,
`outputs/phase5_representation_audit.csv`, `outputs/phase5_anchor_games.csv`,
`outputs/phase5_neighbor_comparison.csv`.

## Research Question

How can Steam games be represented so that nearest neighbors correspond to meaningful game-to-game
similarity? This phase compares structured metadata, lexical (TF-IDF) text similarity, semantic text
embeddings, and a transparent hybrid — not to declare one "best" by an invented metric, but to understand
what each captures and where each fails.

## Why This Is Similarity, Not Personalized Recommendation

This dataset has no user-interaction data: no purchases, per-user ratings, click behavior, or play histories
— only game-level metadata and current-cumulative popularity outcomes (excluded from every representation
here, per Phase 3/4's leakage findings). This phase builds **content-based game discovery** — "games that
describe themselves alike" — never collaborative filtering, personalized recommendation, or recommendation
accuracy, since none of those claims are supportable without interaction data.

## Representation Feasibility

Full table: `outputs/phase5_representation_audit.csv`. Genres (93.9% coverage, 43 labels) and categories
(93.6%, 98 labels) are near-complete and low-cardinality. Tags are richer where present (median 17/game) but
only 60.0% covered catalog-wide. Descriptions are ~94% covered; `about_the_game` and `detailed_description`
are 91.7% byte-identical (redundant — only one carried forward). `about_the_game` contains HTML in ~30% of
rows (cleaned before use).

**A parsing discovery beyond Phase 1's scope:** tags have a third serialization format Phase 1 never
documented — 22,806 rows (16.4% of the raw catalog) store tags as a JSON object mapping tag name to
community vote count (e.g. `{"Farming Sim": 7935, ...}`) rather than a list. The shared `parse_list_field`
utility silently read these as zero tags, undercounting real coverage — including for well-known titles like
*Stardew Valley*. Fixed via a new, additive function, `src/audit_utils.py::parse_tags_field` (genres/
categories were checked and confirmed not to share this issue; `parse_list_field` is unchanged for them).

## Similarity Population

129,847 of 139,076 games (93.4%) after sequential, justified exclusions: 16 missing names, 1,179 pure
creative/productivity software listings (Phase 2's finding), 81 demo listings (name pattern), and 7,953 rows
with literally no genre/category/tag/description content at all. Games with thin-but-real metadata (single
genre, short description, no tags) were deliberately **not** excluded. Saved to
`data/processed/similarity_frame.parquet` (~123 MB) and `data/processed/similarity_embeddings.npy` (~199 MB)
— both git-ignored (matching `data/raw`'s treatment) but fully deterministic and regenerable from
`steam_games.csv`.

## Structured Metadata Representation (A)

Genres, categories, and tags — each L2-normalized per game within its own family before a family-level
scalar weight is applied, so raw label count doesn't mechanically inflate a family's influence.
**Weight sensitivity was tested across three anchors, not asserted**: down-weighting tags to 0.5x
consistently produced broader, less precise neighbors (e.g. Papers, Please pulled in the unrelated *Deponia*
fantasy-comedy series); equal weighting (1.0/1.0/1.0) consistently recovered more thematically precise
neighbors across all three anchors tested, without the occasional regressions seen at 2x tag weight.
**Decision: equal family weighting**, the most interpretable choice and the one supported by evidence rather
than an arbitrary pick. Excludes price, platform, and developer/publisher identity from the core score
(kept separate, per Task 4's guidance that content similarity shouldn't be dominated by studio identity).
Result: a 526-dimension sparse matrix, 8.7 MB.

## TF-IDF Representation (B)

`about_the_game_clean` (HTML-stripped, truncated to 2,000 chars), `min_df=5`, `max_df=0.5`, unigrams+bigrams,
capped at 40,000 features (kept sparse throughout — no dense matrix). Genuinely useful matches surfaced
(Stardew Valley → *Caravan Village: Farming Life*, *Coral Island*), but franchise/title-token dominance is a
real, visible failure mode (see below).

## Semantic Embedding Representation (C)

`all-MiniLM-L6-v2` via `sentence-transformers` — a compact (~90MB), locally-run, CPU-only model; no paid API,
no GPU required. Ran successfully in this environment (no fallback needed). Encoded `short_description`
(falling back to a truncated `about_the_game` for the ~0.3% of games missing it), producing a 129,847 x 384
float32 matrix (~199 MB), normalized so cosine similarity is a plain dot product. **Runtime note:** the full
encode took 22.4 minutes on this machine (CPU) — longer than an initial 2,000-row sample suggested, and
exceeded the notebook execution environment's 900-second per-cell timeout, so embeddings were precomputed
once to a local cache file and loaded (near-instantly) inside the notebook thereafter; this is documented
directly in the notebook rather than silently worked around.

## Hybrid Representation (D)

`hybrid = alpha * semantic_similarity + (1 - alpha) * structured_similarity`, swept over alpha in
{0.00, 0.25, 0.50, 0.75, 1.00} for sensitivity analysis only — never tuned against invented ground truth.
**A scale-mismatch bug was caught before trusting alpha at face value**: raw structured scores range 0-3.0
while semantic cosine similarity ranges roughly -0.2 to 1.0 — blending directly at `alpha=0.5` would give
structured similarity ~4x its nominal influence. **Fixed** by rescaling structured scores by the sum of
family weights (3.0) before blending, confirmed by re-running the alpha sweep and observing a genuine,
gradual transition (fig. 6) rather than one input dominating until alpha=0.75+. **Default: alpha=0.5.**

## Evaluation Without User Ground Truth

No purchases, ratings, or interaction history exist, so nothing here is reported as recommendation accuracy,
precision, recall, or NDCG. Two diagnostic categories, kept explicitly separate: **internal consistency**
(representation A's genre/category/tag overlap — near-tautological, since those labels built it) and
**cross-representation agreement** (B's and C's overlap with genre/category/tag labels they never saw — the
closest thing to independent evidence available). Genre Jaccard@10: A=0.916 (internal), B=0.479, C=0.422
(both real cross-representation agreement, well above chance).

## Representation Comparison

| Representation | Genre Jaccard@10 | Category Jaccard@10 | Tag Jaccard@10 | Retrieval time |
|---|---|---|---|---|
| A structured | 0.916 (internal) | 0.565 (internal) | 0.457 (internal) | 16.6 ms |
| B TF-IDF | 0.479 | 0.299 | 0.198 | 44.1 ms |
| C semantic | 0.422 | 0.277 | 0.167 | 5.0 ms |
| D hybrid (a=0.5) | 0.802 | 0.449 | 0.383 | ~20 ms |

**Structured vs. semantic scores for the same candidates: Pearson r = -0.27** — weakly *negatively*
correlated, not merely uncorrelated. The two representations capture genuinely different, even mildly
opposing, notions of "similar" — the strongest quantitative evidence in this notebook for why a hybrid adds
real information rather than averaging redundant signal.

## Failure Modes

- **Structured (A):** broad-label collapse — down-weighted-tags Stardew Valley neighbors included a cleaning
  simulator (*Viscera Cleanup Detail*) and a horror title, sharing only coarse genre labels.
- **TF-IDF (B):** franchise/title-token dominance — Dark Souls III's and Counter-Strike 2's top TF-IDF
  neighbors are dominated by other entries in the same franchise, driven by shared proper nouns and repeated
  marketing language rather than independent content description.
- **Semantic (C), the clearest failure case:** *Disco Elysium - The Final Cut*'s neighbors are `Angels That
  Kill - The Final Cut`, `Deal of the Dead Final Cut`, `The Last Oricru - Final Cut` — unrelated games sharing
  only the edition label "Final Cut," which appears directly in Disco Elysium's own `short_description`
  ("...is a groundbreaking role playing game...") and evidently dominates the resulting embedding.
- **Hybrid (D):** balances rather than eliminates — the Hades case study shows it genuinely blends both
  failure-mode-prone signals rather than resolving either.

## Popularity Bias

**Opposite of the hypothesized direction.** Every representation shows a strongly *negative* median
log-review-ratio (neighbor vs. anchor): -4.4 (A), -9.6 (B), -9.9 (C), -5.6 (D) — retrieval is biased **toward
less-visible, not more-visible, games**, with 0-2% of neighbors more reviewed than their anchor across all
four representations. Plausible explanation (checked against established findings, not newly asserted): the
20 anchors were deliberately chosen to include several highly-reviewed titles, while the catalog itself is
dominated by its long tail (Phase 2); any generic content match statistically lands on a long-tail game more
often than not. Text-based representations (B, C) show this most strongly. Reported as a
representation/catalog-composition characteristic, not corrected or optimized away — for a discovery tool
this is arguably a desirable property.

## Case Studies

1. **Hades** — structured metadata recovers Supergiant Games' entire other catalog (`Hades II`, `Bastion`,
   `Transistor`, `Pyre`) *without developer identity ever being a feature*; pure semantic embeddings surface
   thematically-related-but-gameplay-unconfirmed titles (`Bloody Heaven 2`, `Black Myth: Heaven`). The hybrid
   (after the scale fix) genuinely blends both.
2. **Disco Elysium - The Final Cut — failure case.** Semantic neighbors are dominated by unrelated games
   sharing only the "Final Cut" edition label; structured metadata performs much better (`Pillars of Eternity
   II`, `The Legend of Heroes`).
3. **DARK SOULS III** — same-franchise entries dominate the default top-4; the lightweight
   `is_likely_same_franchise` suppression heuristic cleanly reveals cross-franchise discovery
   (`Monster Hunter: World`, `ELDEN RING`, `Toukiden 2`) instead.
4. **Stardew Valley — success case.** All three base representations converge on genuine farming/life-sim
   titles, the scenario that most validates the overall approach.
5. **Papers, Please** — directly validates the Task 5 tag-weighting decision: down-weighted tags produced the
   thematically-wrong *Deponia* series; equal weighting recovered genuinely political-themed matches.

## Final Representation Decision

**D. Hybrid (alpha=0.5) as the recommended default — not because it automatically wins, but because it best
balances demonstrated failure modes without introducing a new one**, closer to "D with E's caveat" than a
clean single winner: every pure representation retains a clearly evidenced comparative advantage (structured
recovers a "spiritual catalog" without developer identity; TF-IDF sidesteps semantic's edition-label
vulnerability; semantic captures theme beyond lexical overlap), so `find_similar_games` keeps all four
representations fully selectable rather than hiding three behind the hybrid default.

## What "Similar" Means in This Project

Two games are "similar" if they **describe themselves alike** — shared genre/category/tag labels and/or
related description text. This is a claim about content description, never about actual gameplay similarity
(no mechanics/telemetry data exists to check against), player preference, or commercial comparability
(popularity was excluded from every representation, and retrieval is if anything biased away from it).

## Limitations

- No independent ground truth exists for any quantitative claim here.
- Multilingual content is not specially handled; MiniLM is primarily English-optimized.
- The franchise-suppression heuristic is intentionally simple and will both under- and over-trigger.
- The 20-anchor set, while deliberately diverse, is a sample, not exhaustive coverage.
- Semantic embeddings can be misled by incidental text (the Disco Elysium case) — not solved here.
- Popularity bias exists and was measured, not corrected.
- This reflects the 2026-08-28 catalog snapshot, like every other phase of this project.

## Recommended Next Phase

Combine Phase 4's cohort-relative visibility with this phase's content similarity to ask a genuinely new,
still-descriptive question: among games structurally similar to a given title, which substantially over- or
under-perform their content-similarity peers in visibility — a natural extension that stays within this
project's established non-causal, cohort-aware methodology rather than opening a separate modeling track.
