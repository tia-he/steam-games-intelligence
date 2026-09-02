"""
Reusable transforms for Phase 4 -- Cohort-Aware Visibility Modeling.

Builds on Phase 1's parsers (src/audit_utils.py) and Phase 2's derived table
(src/market_utils.py). Nothing here touches outcome fields (positive,
negative, total_reviews, estimated_owners, recommendations, peak_ccu,
playtime) -- see outputs/phase3_leakage_map.csv for the authoritative ruling
this module is built to respect.
"""
import bisect
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score, average_precision_score, log_loss, brier_score_loss,
    precision_score, recall_score, f1_score,
)


# --------------------------------------------------------------------------
# Multi-label (genre/category/tag) encoding
# --------------------------------------------------------------------------

def select_vocab_by_train_count(train_lists: pd.Series, min_count: int) -> list:
    """Labels appearing >= min_count times in TRAIN rows only. Any frequency
    cutoff must be chosen this way -- never using validation/test rows -- so
    the vocabulary itself cannot leak future-cohort information.
    """
    c = Counter()
    for v in train_lists:
        if v is not None and hasattr(v, '__iter__'):
            for item in v:
                c[item] += 1
    return sorted([item for item, n in c.items() if n >= min_count])


def multi_hot(list_col: pd.Series, vocab: list, prefix: str) -> pd.DataFrame:
    """0/1 DataFrame, one column per vocab entry. Labels outside vocab
    (rare, train-invisible) are silently dropped -- not an 'Other' bucket,
    since an unordered multi-label 'other' flag is not obviously meaningful.
    """
    vocab_set = set(vocab)
    idx = {v: i for i, v in enumerate(vocab)}
    out = np.zeros((len(list_col), len(vocab)), dtype=np.int8)
    for row, v in enumerate(list_col.values):
        if v is None or not hasattr(v, '__iter__'):
            continue
        for item in v:
            if item in vocab_set:
                out[row, idx[item]] = 1
    cols = [f"{prefix}__{v}" for v in vocab]
    return pd.DataFrame(out, columns=cols, index=list_col.index)


# --------------------------------------------------------------------------
# Point-in-time developer/publisher prior-release-count
# --------------------------------------------------------------------------

def compute_prior_release_counts(entity_release_dates: pd.DataFrame, entity_col: str,
                                  date_col: str = 'release_date') -> pd.DataFrame:
    """For each (entity, release_date) row, count how many of that SAME
    entity's releases have a strictly earlier release_date. Same-day
    releases never count each other (strict '<', not a tie-broken '<=').

    entity_release_dates: one row per (game, entity) link, e.g. the exploded
    developer-list table -- NOT one row per game. Pass the full catalog's
    history (not just the modeling population) so a developer active before
    2017 gets credit for those earlier releases.

    Returns the input frame with a `prior_count` column added.
    """
    df = entity_release_dates.copy()
    df = df.sort_values([entity_col, date_col]).reset_index(drop=True)
    prior = np.empty(len(df), dtype=np.int64)
    for entity, group in df.groupby(entity_col, sort=False):
        dates = group[date_col].values  # already sorted ascending within group
        idx = group.index.values
        for pos, row_idx in enumerate(idx):
            # bisect_left on the sorted own-dates array gives the count of
            # this entity's OTHER releases strictly before this one's date
            prior[row_idx] = bisect.bisect_left(dates, dates[pos])
    df['prior_count'] = prior
    return df


def aggregate_entity_feature_per_game(exploded: pd.DataFrame, app_id_col: str,
                                       value_col: str, agg: str = 'max') -> pd.Series:
    """Collapse a per-(game, entity) value back to one value per game, for
    games with multiple credited developers/publishers. agg='max' is the
    default: at least one credited entity has this much prior output --
    documented rationale in the Phase 4 notebook (mean would understate a
    single experienced studio's presence in a multi-studio credit, and is
    identical to max for the very common single-developer case anyway).
    """
    if agg == 'max':
        return exploded.groupby(app_id_col)[value_col].max()
    elif agg == 'mean':
        return exploded.groupby(app_id_col)[value_col].mean()
    raise ValueError(f"unsupported agg: {agg}")


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def precision_at_top_fraction(y_true: np.ndarray, y_score: np.ndarray, fraction: float) -> float:
    """Precision among the top `fraction` of games by predicted score."""
    n = len(y_true)
    k = max(1, int(round(n * fraction)))
    order = np.argsort(-y_score)
    top_k = order[:k]
    return float(np.mean(np.asarray(y_true)[top_k]))


def threshold_for_predicted_positive_rate(y_prob, target_rate: float = 0.20) -> float:
    """The probability cutoff such that approximately `target_rate` of the given
    (validation-only) predictions would be flagged positive. Used as the Task 7
    threshold policy: pick the cutoff on VALIDATION, matching the target's own
    'top 20% within cohort' framing, then reuse that fixed number at test time.
    """
    return float(np.quantile(y_prob, 1 - target_rate))


def compute_metrics(y_true, y_prob, threshold: float) -> dict:
    """Threshold-independent + threshold-dependent metrics in one place, so
    every reported table is computed the same way."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob)
    y_pred = (y_prob >= threshold).astype(int)
    return {
        'n': len(y_true),
        'prevalence': float(y_true.mean()),
        'roc_auc': roc_auc_score(y_true, y_prob),
        'pr_auc': average_precision_score(y_true, y_prob),
        'log_loss': log_loss(y_true, y_prob, labels=[0, 1]),
        'brier': brier_score_loss(y_true, y_prob),
        'threshold': threshold,
        'precision': precision_score(y_true, y_pred, zero_division=0),
        'recall': recall_score(y_true, y_pred, zero_division=0),
        'f1': f1_score(y_true, y_pred, zero_division=0),
        'precision_at_top10pct': precision_at_top_fraction(y_true, y_prob, 0.10),
        'precision_at_top20pct': precision_at_top_fraction(y_true, y_prob, 0.20),
    }


def reliability_curve(y_true, y_prob, n_bins: int = 10) -> pd.DataFrame:
    """Equal-width bins in [0,1]; returns per-bin mean predicted prob, mean
    observed rate, and count (empty bins dropped)."""
    y_true = np.asarray(y_true).astype(float)
    y_prob = np.asarray(y_prob)
    bins = np.linspace(0, 1, n_bins + 1)
    bin_idx = np.digitize(y_prob, bins[1:-1], right=True)
    rows = []
    for b in range(n_bins):
        mask = bin_idx == b
        if mask.sum() == 0:
            continue
        rows.append({
            'bin': b, 'n': int(mask.sum()),
            'mean_predicted': float(y_prob[mask].mean()),
            'mean_observed': float(y_true[mask].mean()),
        })
    return pd.DataFrame(rows)
