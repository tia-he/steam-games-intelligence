"""
Reusable transforms for Phase 6 -- Similar-Game Peer Benchmarking & Portfolio Synthesis.

Connects Phase 5's content-based similarity (src/similarity_utils.py) with Phase 3/4's
cohort-relative visibility measure (data/processed/modeling_frame.parquet). This module
builds peer sets from CONTENT SIMILARITY ONLY -- no popularity/outcome field is ever used
to select a peer, only to summarize peer visibility *after* the peer set is fixed.

Everything here is descriptive peer benchmarking, never causal inference, a new predictive
target, or a personalized recommender. See outputs/phase6_peer_benchmarking_findings.md.
"""
import re

import numpy as np
import pandas as pd

from similarity_utils import _TITLE_NOISE_WORDS


# --------------------------------------------------------------------------
# Population alignment (Part C)
# --------------------------------------------------------------------------

def build_overlap_population(similarity_frame: pd.DataFrame, modeling_frame: pd.DataFrame) -> pd.DataFrame:
    """Inner-join the Phase 5 similarity population (129,847 games) with the Phase 3/4
    modeling population (2017-2023, n=67,241) on app_id. Both a valid content
    representation (Phase 5) and a valid cohort-relative visibility measure (Phase 3/4,
    which only exists for 2017-2023 releases) are required for peer benchmarking, so
    peers and focal games are both restricted to this overlap set -- see Part C.
    """
    keep_cols = ['app_id', 'name', 'release_date', 'cohort_release_year',
                 'target_pct_within_cohort', 'target_top20pct_visibility',
                 'price_current', 'price_status_current']
    merged = similarity_frame.merge(modeling_frame[keep_cols], on='app_id', how='inner',
                                     suffixes=('', '_mf'))
    merged = merged.drop(columns=['name_mf'], errors='ignore').reset_index(drop=True)
    return merged


# --------------------------------------------------------------------------
# Franchise / duplicate suppression (lightweight, vectorized)
# --------------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Za-z']+")


def franchise_key(name: str) -> str:
    """First significant (non-noise, length>=4) lowercase word in a title, or '' if
    none exists. Same rule as similarity_utils.is_likely_same_franchise's primary
    check ('DARK SOULS III' vs 'DARK SOULS: REMASTERED' share the key 'dark'), applied
    as a precomputed per-game key rather than a pairwise function so that franchise
    suppression can be vectorized across tens of thousands of candidates per query
    instead of evaluated pair-by-pair in a Python loop. This is a documented
    simplification of Phase 5's heuristic for scale, not full entity resolution --
    it will both under- and over-trigger, same as the original.
    """
    if not isinstance(name, str):
        return ''
    words = [w.lower() for w in _WORD_RE.findall(name)
             if len(w) >= 4 and w.lower() not in _TITLE_NOISE_WORDS]
    return words[0] if words else ''


# --------------------------------------------------------------------------
# Batched top-K retrieval over the overlap population
# --------------------------------------------------------------------------

def _apply_exclusions(scores: np.ndarray, b_offsets: np.ndarray, franchise_keys: np.ndarray,
                       names: np.ndarray, suppress_duplicates: bool, year_mask=None) -> None:
    """In-place: -inf out self, (optionally) same-franchise-key / exact-duplicate-name
    candidates, and (optionally) candidates outside a per-query temporal window."""
    rows = np.arange(scores.shape[0])
    scores[rows, b_offsets] = -np.inf
    if suppress_duplicates:
        b_keys = franchise_keys[b_offsets]
        b_names = names[b_offsets]
        for r in range(scores.shape[0]):
            key = b_keys[r]
            if key:
                scores[r, franchise_keys == key] = -np.inf
            scores[r, names == b_names[r]] = -np.inf
    if year_mask is not None:
        scores[~year_mask] = -np.inf


def _top_k_from_scores(scores: np.ndarray, k_over: int) -> tuple:
    row_idx = np.arange(scores.shape[0])[:, None]
    part = np.argpartition(-scores, k_over, axis=1)[:, :k_over]
    part_scores = scores[row_idx, part]
    order = np.argsort(-part_scores, axis=1)
    return part[row_idx, order], part_scores[row_idx, order]


def batched_top_k(query_mat: np.ndarray, corpus_mat: np.ndarray, query_offsets: np.ndarray,
                   franchise_keys: np.ndarray, names: np.ndarray, k_over: int = 50,
                   batch_size: int = 1500, suppress_duplicates: bool = True) -> tuple:
    """Single-representation dense batched matmul retrieval: query_mat (n_query x d,
    may be a subset of corpus_mat's rows) against corpus_mat (n_corpus x d), both
    assumed already scaled so a dot product is the intended similarity score.
    `query_offsets` gives each query row's own position in the corpus (excluded from
    its own neighbor list). Returns (neighbor_idx, neighbor_scores), each
    (n_query x k_over), sorted descending, self and (optionally) same-franchise-key /
    exact-duplicate-name candidates excluded.
    """
    n_query = query_mat.shape[0]
    n_corpus = corpus_mat.shape[0]
    k_over = min(k_over, n_corpus - 1)
    out_idx = np.empty((n_query, k_over), dtype=np.int32)
    out_score = np.empty((n_query, k_over), dtype=np.float32)
    corpus_mat_f = corpus_mat.astype(np.float32, copy=False)
    for start in range(0, n_query, batch_size):
        end = min(start + batch_size, n_query)
        batch = query_mat[start:end].astype(np.float32, copy=False)
        scores = batch @ corpus_mat_f.T  # (b, n_corpus)
        _apply_exclusions(scores, query_offsets[start:end], franchise_keys, names, suppress_duplicates)
        out_idx[start:end], out_score[start:end] = _top_k_from_scores(scores, k_over)
    return out_idx, out_score


def batched_hybrid_top_k(query_struct: np.ndarray, corpus_struct: np.ndarray,
                          query_sem: np.ndarray, corpus_sem: np.ndarray, query_offsets: np.ndarray,
                          franchise_keys: np.ndarray, names: np.ndarray, alpha: float = 0.5,
                          struct_weight_sum: float = 3.0, k_over: int = 50, batch_size: int = 1500,
                          suppress_duplicates: bool = True, corpus_release_years=None,
                          query_release_years=None, year_window: int = None) -> tuple:
    """Hybrid retrieval combining structured and semantic SIMILARITY SCORES (not raw
    feature vectors, which are not directly comparable across representations):
    hybrid_score = alpha * semantic_score + (1 - alpha) * (structured_score / 3.0),
    the Phase 5 scale-corrected blend (raw structured dot products range 0-3.0 under
    equal 1/1/1 family weights; dividing by 3.0 puts both inputs on a comparable
    ~0-1 scale before blending). alpha=1.0 / 0.0 recover pure semantic / structured
    retrieval from the same code path, used for the Task 6 representation-sensitivity
    comparison. query_* may be a subset of corpus_* (e.g. a sample for a sensitivity
    check run against the full corpus); `query_offsets` gives each query row's own
    position within the corpus. `year_window`, if given with the release-year arrays,
    additionally restricts each query's candidates to release years within
    +/- year_window (Task 3).
    """
    n_query = query_struct.shape[0]
    n_corpus = corpus_struct.shape[0]
    k_over = min(k_over, n_corpus - 1)
    out_idx = np.empty((n_query, k_over), dtype=np.int32)
    out_score = np.empty((n_query, k_over), dtype=np.float32)
    qs_f = query_struct.astype(np.float32, copy=False)
    cs_f = corpus_struct.astype(np.float32, copy=False)
    qe_f = query_sem.astype(np.float32, copy=False)
    ce_f = corpus_sem.astype(np.float32, copy=False)
    for start in range(0, n_query, batch_size):
        end = min(start + batch_size, n_query)
        struct_scores = qs_f[start:end] @ cs_f.T
        sem_scores = qe_f[start:end] @ ce_f.T
        scores = alpha * sem_scores + (1 - alpha) * (struct_scores / struct_weight_sum)
        year_mask = None
        if corpus_release_years is not None and query_release_years is not None and year_window is not None:
            b_years = query_release_years[start:end][:, None]
            year_mask = np.abs(corpus_release_years[None, :] - b_years) <= year_window
        _apply_exclusions(scores, query_offsets[start:end], franchise_keys, names,
                           suppress_duplicates, year_mask)
        out_idx[start:end], out_score[start:end] = _top_k_from_scores(scores, k_over)
    return out_idx, out_score


# --------------------------------------------------------------------------
# Peer-relative visibility gap
# --------------------------------------------------------------------------

def peer_benchmark_table(df: pd.DataFrame, neighbor_idx: np.ndarray, neighbor_scores: np.ndarray,
                          k_list=(10, 20, 50)) -> pd.DataFrame:
    """For each query row i, and each K in k_list, compute:
      - peer_visibility_median: median target_pct_within_cohort among the top-K peers
      - peer_visibility_gap: query's own percentile minus peer_visibility_median
      - mean/median/min top-K similarity, similarity spread (max-min)
    neighbor_idx/neighbor_scores must already be sorted descending by score and have
    at least max(k_list) columns. Purely descriptive -- see module docstring.
    """
    vis = df['target_pct_within_cohort'].values
    max_k = max(k_list)
    peer_vis_all = vis[neighbor_idx[:, :max_k]]  # (n, max_k)
    peer_score_all = neighbor_scores[:, :max_k]

    out = {'app_id': df['app_id'].values, 'name': df['name'].values,
           'release_year': df['cohort_release_year'].values,
           'visibility_percentile': vis}
    for k in k_list:
        pv = peer_vis_all[:, :k]
        ps = peer_score_all[:, :k]
        med = np.median(pv, axis=1)
        out[f'peer_visibility_median_k{k}'] = med
        out[f'peer_visibility_gap_k{k}'] = vis - med
        out[f'mean_peer_similarity_k{k}'] = ps.mean(axis=1)
        out[f'median_peer_similarity_k{k}'] = np.median(ps, axis=1)
        out[f'min_peer_similarity_k{k}'] = ps.min(axis=1)
        out[f'similarity_spread_k{k}'] = ps.max(axis=1) - ps.min(axis=1)
    return pd.DataFrame(out)


def spearman_agreement(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation between two arrays of the same peer-relative
    quantity computed under different design choices (K, representation, temporal
    restriction, franchise suppression) -- used for the Task 6 robustness check."""
    from scipy.stats import spearmanr
    r, _ = spearmanr(a, b)
    return float(r)
