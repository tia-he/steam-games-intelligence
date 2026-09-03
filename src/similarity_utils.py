"""
Reusable transforms for Phase 5 -- Game Representation & Content-Based Similarity.

Content-based similarity only. No user-interaction data exists in this dataset (no purchases, ratings,
playtime-per-user, click behavior), so nothing here implements or claims collaborative filtering or
personalized recommendation -- see outputs/phase5_similarity_findings.md.

No popularity/outcome field (total_reviews, positive, negative, estimated_owners, recommendations,
peak_ccu, playtime, the Phase 4 target) is used to construct any representation in this module.
"""
import re
from collections import Counter

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize as sk_normalize

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')


def clean_text(text) -> str:
    """Strip HTML tags/entities and normalize whitespace. Deliberately light-touch --
    does not stem, remove stopwords, or strip punctuation (TfidfVectorizer handles
    tokenization); the goal here is only to remove markup noise, not game terminology.
    """
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return ''
    text = str(text)
    text = _HTML_TAG_RE.sub(' ', text)
    text = text.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    text = _WHITESPACE_RE.sub(' ', text).strip()
    return text


# --------------------------------------------------------------------------
# Structured (genre/category/tag) representation
# --------------------------------------------------------------------------

def build_vocab(list_col: pd.Series, min_count: int = 1) -> list:
    c = Counter()
    for v in list_col:
        if v is not None and hasattr(v, '__iter__') and not isinstance(v, str):
            for item in v:
                c[item] += 1
    return sorted([item for item, n in c.items() if n >= min_count])


def multi_hot_l2(list_col: pd.Series, vocab: list) -> sparse.csr_matrix:
    """Multi-hot encode, then L2-normalize each row within this block, so a game
    with 2 active labels and a game with 20 active labels each contribute a unit-
    norm vector to their family -- label *count* doesn't by itself inflate a
    family's influence before the family-level weight is applied.
    """
    idx = {v: i for i, v in enumerate(vocab)}
    rows, cols = [], []
    for r, v in enumerate(list_col.values):
        if v is None or not hasattr(v, '__iter__') or isinstance(v, str):
            continue
        for item in v:
            j = idx.get(item)
            if j is not None:
                rows.append(r)
                cols.append(j)
    data = np.ones(len(rows), dtype=np.float32)
    mat = sparse.csr_matrix((data, (rows, cols)), shape=(len(list_col), len(vocab)))
    return sk_normalize(mat, norm='l2', axis=1)


def build_structured_representation(df: pd.DataFrame, genre_vocab, category_vocab, tag_vocab,
                                     weights: dict) -> sparse.csr_matrix:
    """Concatenate L2-normalized genre/category/tag blocks with family-level scalar
    weights (see Phase 5 notebook Task 5 for the sensitivity test behind the
    default weights). Cosine similarity on the result already accounts for each
    family's relative weight without needing a further outer normalization.
    """
    g = multi_hot_l2(df['genre_list'], genre_vocab) * weights.get('genre', 1.0)
    c = multi_hot_l2(df['category_list'], category_vocab) * weights.get('category', 1.0)
    t = multi_hot_l2(df['tag_list'], tag_vocab) * weights.get('tag', 1.0)
    return sparse.hstack([g, c, t], format='csr')


# --------------------------------------------------------------------------
# TF-IDF representation
# --------------------------------------------------------------------------

def build_tfidf_representation(texts: pd.Series, max_features=40000, min_df=5, max_df=0.5,
                                ngram_range=(1, 2)):
    vectorizer = TfidfVectorizer(max_features=max_features, min_df=min_df, max_df=max_df,
                                  ngram_range=ngram_range, stop_words='english', sublinear_tf=True)
    matrix = vectorizer.fit_transform(texts)  # already L2-normalized by TfidfVectorizer
    return matrix, vectorizer


# --------------------------------------------------------------------------
# Retrieval (no dense N x N matrix -- one query row against the corpus at a time)
# --------------------------------------------------------------------------

def top_k_similar(query_vec, matrix, k: int, exclude_idx=None):
    """query_vec: 1 x d (sparse or dense), matrix: N x d (same type family), both
    assumed L2-normalized per row so dot product = cosine similarity. Returns
    (indices, scores) for the top-k matches, excluding exclude_idx (the query's
    own row, if it's part of the corpus).
    """
    if sparse.issparse(matrix):
        scores = (matrix @ query_vec.T).toarray().ravel()
    else:
        scores = matrix @ np.asarray(query_vec).ravel()
    if exclude_idx is not None:
        scores = scores.copy()
        scores[exclude_idx] = -np.inf
    k = min(k, len(scores) - 1)
    top_idx = np.argpartition(-scores, k)[:k]
    top_idx = top_idx[np.argsort(-scores[top_idx])]
    return top_idx, scores[top_idx]


def row_vec(matrix, idx):
    """A single row as a 1 x d matrix (sparse-safe)."""
    return matrix[idx]


# --------------------------------------------------------------------------
# Hybrid scoring
# --------------------------------------------------------------------------

def hybrid_scores(struct_scores: np.ndarray, text_scores: np.ndarray, alpha: float) -> np.ndarray:
    """hybrid = alpha * text_similarity + (1 - alpha) * structured_similarity."""
    return alpha * text_scores + (1 - alpha) * struct_scores


# --------------------------------------------------------------------------
# Name/app_id resolution
# --------------------------------------------------------------------------

_TITLE_NOISE_WORDS = {
    'the', 'edition', 'remastered', 'deluxe', 'goty', 'directors', 'cut', 'ultimate',
    'complete', 'collection', 'definitive', 'enhanced', 'special', 'prologue', 'demo',
}


def is_likely_same_franchise(anchor_name: str, neighbor_name: str) -> bool:
    """Lightweight, documented heuristic (not full entity resolution): true if the
    neighbor's title starts with the anchor's first significant (non-noise,
    length>=4) word, e.g. 'DARK SOULS III' vs 'DARK SOULS: REMASTERED', or if one
    title is a prefix of the other after stripping edition/remaster noise words.
    Deliberately simple and over-inclusive is fine here -- it only feeds an
    optional suppression filter, not a correctness-critical computation.
    """
    def sig_words(s):
        return [w.lower() for w in re.findall(r"[A-Za-z']+", s) if len(w) >= 4 and w.lower() not in _TITLE_NOISE_WORDS]

    a_words, n_words = sig_words(anchor_name), sig_words(neighbor_name)
    if not a_words or not n_words:
        return False
    return a_words[0] == n_words[0]


def resolve_query(df: pd.DataFrame, query) -> list:
    """Return a list of matching row-positions (not app_ids) for an app_id or an
    exact (case-insensitive) name query. Never silently picks one row among
    duplicates -- the caller decides how to handle len(result) > 1.
    """
    if isinstance(query, (int, np.integer)):
        matches = np.where(df['app_id'].values == query)[0]
    else:
        matches = np.where(df['name'].str.lower().values == str(query).lower())[0]
    return matches.tolist()


# --------------------------------------------------------------------------
# Explanation
# --------------------------------------------------------------------------

def explain_overlap(df: pd.DataFrame, i: int, j: int) -> dict:
    gi, gj = set(df['genre_list'].iloc[i] or []), set(df['genre_list'].iloc[j] or [])
    ci, cj = set(df['category_list'].iloc[i] or []), set(df['category_list'].iloc[j] or [])
    ti, tj = set(df['tag_list'].iloc[i] or []), set(df['tag_list'].iloc[j] or [])
    return {
        'shared_genres': sorted(gi & gj),
        'shared_categories': sorted(ci & cj),
        'shared_tags': sorted(ti & tj),
    }
