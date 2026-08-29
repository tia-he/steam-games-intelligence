"""
Reusable transforms for Phase 2 — Steam Market Analytics.

Builds on the parsers discovered during Phase 1 (see src/audit_utils.py) rather
than re-deriving parsing logic. Everything here is deterministic given
steam_games.csv, so games_clean.parquet can always be regenerated from source.
"""
import numpy as np
import pandas as pd
from collections import Counter

from audit_utils import parse_list_field, parse_estimated_owners

# Empirically observed Steam price points (see Phase 2 pricing investigation):
# P75 paid price = $9.99, P90 = $19.99; tier edges chosen at recognizable
# storefront price breaks that also line up with these percentiles. Free
# (price == 0) is handled as its own tier outside the cut, since $0 is not a
# left-open interval boundary of the paid tiers.
PAID_TIER_EDGES = [0, 5, 10, 20, 40, np.inf]
PAID_TIER_LABELS = ["$0.01-4.99", "$5-9.99", "$10-19.99", "$20-39.99", "$40+"]
PRICE_TIER_LABELS = ["Free"] + PAID_TIER_LABELS


def add_release_year(df: pd.DataFrame, date_col: str = "release_date") -> pd.Series:
    """Parse release_date and return release_year as float (NaN if unparsable)."""
    parsed = pd.to_datetime(df[date_col], errors="coerce")
    return parsed.dt.year.astype("float")


def add_review_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add total_reviews = positive + negative and positive_ratio (NaN if 0 reviews)."""
    df = df.copy()
    total = df["positive"].fillna(0) + df["negative"].fillna(0)
    df["total_reviews"] = total
    df["positive_ratio"] = np.where(total > 0, df["positive"] / total, np.nan)
    return df


def add_ownership_midpoint(df: pd.DataFrame) -> pd.DataFrame:
    """Parse estimated_owners into own_lo/own_hi/own_mid.

    own_mid is a coarse-bucket midpoint, not a precise ownership count
    (Phase 1: only 27 distinct buckets, ~82% of the catalog in the bottom two).
    """
    df = df.copy()
    parsed = df["estimated_owners"].apply(parse_estimated_owners)
    df["own_lo"] = parsed.apply(lambda t: t[0])
    df["own_hi"] = parsed.apply(lambda t: t[1])
    df["own_mid"] = parsed.apply(lambda t: t[2])
    return df


def assign_price_tier(price: pd.Series) -> pd.Series:
    """Bucket current price into empirically-grounded tiers: Free plus five
    paid tiers (see PAID_TIER_EDGES)."""
    paid_tier = pd.cut(price, bins=PAID_TIER_EDGES, labels=PAID_TIER_LABELS,
                        right=False, include_lowest=True).astype(object)
    label = np.where(price == 0, "Free", paid_tier)
    return pd.Categorical(label, categories=PRICE_TIER_LABELS, ordered=True)


def explode_list_counts(series_of_lists: pd.Series) -> Counter:
    """Flat item counter over a column of parsed list values (e.g. genre_list)."""
    c = Counter()
    for v in series_of_lists:
        if isinstance(v, list):
            for item in v:
                c[item] += 1
    return c


def genre_prevalence_by_year(df: pd.DataFrame, genres, list_col: str = "genre_list",
                              year_col: str = "release_year") -> pd.DataFrame:
    """Long-form (year, genre, n_with_genre, n_releases, prevalence) table.

    prevalence = share of that year's releases carrying the genre label; games
    with multiple genres are counted in every row they qualify for, so
    prevalence values are NOT mutually-exclusive market shares and can sum
    above 1 within a year.
    """
    rows = []
    for yr, g in df.groupby(year_col):
        n = len(g)
        for genre in genres:
            has = g[list_col].apply(lambda v: genre in v if isinstance(v, list) else False)
            rows.append({"year": yr, "genre": genre, "n_with_genre": int(has.sum()),
                         "n_releases": n, "prevalence": has.mean()})
    return pd.DataFrame(rows)


def concentration_stats(counts: pd.Series) -> dict:
    """Catalog-count concentration diagnostics for a developer/publisher-style
    counter (counts indexed by entity, one row per unique entity).

    NOTE: this measures release-count / catalog concentration, not revenue or
    economic market share.
    """
    total = counts.sum()
    sorted_counts = counts.sort_values(ascending=False)
    shares = sorted_counts / total
    hhi = (shares ** 2).sum() * 10000
    return {
        "n_entities": len(counts),
        "n_game_links": int(total),
        "share_single_game_entities": float((counts == 1).mean()),
        "top10_share": float(shares.head(10).sum()),
        "top50_share": float(shares.head(50).sum()),
        "hhi": float(hhi),
    }


def cohort_genre_median(df: pd.DataFrame, genres, outcome_col: str,
                         list_col: str = "genre_list") -> pd.Series:
    """Median of outcome_col per genre within whatever subset of df is passed in
    (caller pre-filters to a release-year cohort). Multi-label: a game can
    contribute to more than one genre's median.
    """
    out = {}
    for genre in genres:
        mask = df[list_col].apply(lambda v: genre in v if isinstance(v, list) else False)
        out[genre] = df.loc[mask, outcome_col].median()
    return pd.Series(out)


def build_games_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Produce the normalized, analysis-ready game-level table used throughout
    the Phase 2 notebook. Deterministic given steam_games.csv + audit_utils
    parsers. Does not treat own_mid as ground-truth ownership or price as
    launch price -- see notebook markdown for interpretation caveats.
    """
    out = pd.DataFrame({
        "app_id": df["app_id"],
        "name": df["name"],
    })
    out["release_year"] = add_release_year(df)
    out["price"] = df["price"]
    out["price_status"] = df["price_status"]
    out["price_tier"] = assign_price_tier(df["price"])
    out["genre_list"] = df["genres"].apply(parse_list_field)
    out["category_list"] = df["categories"].apply(parse_list_field)
    out["developers_list"] = df["developers"].apply(parse_list_field)
    out["publishers_list"] = df["publishers"].apply(parse_list_field)
    out["positive"] = df["positive"]
    out["negative"] = df["negative"]
    rm = add_review_metrics(df)
    out["total_reviews"] = rm["total_reviews"]
    out["positive_ratio"] = rm["positive_ratio"]
    own = add_ownership_midpoint(df)
    out["own_lo"] = own["own_lo"]
    out["own_hi"] = own["own_hi"]
    out["own_mid"] = own["own_mid"]
    out["peak_ccu"] = df["peak_ccu"]
    out["recommendations"] = df["recommendations"]
    out["average_playtime_forever"] = df["average_playtime_forever"]
    return out
