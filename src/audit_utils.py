"""
Reusable parsing / loading utilities for the Phase 1 data audit.

These functions encode facts discovered empirically during the audit
(e.g. two mixed serialization formats for list-like fields) rather than
assumptions from the source documentation.
"""
import ast
import json
import os
import re
from collections import Counter

import numpy as np
import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
GAMES_PATH = os.path.join(RAW_DIR, "steam_games.csv")
REVIEWS_PATH = os.path.join(RAW_DIR, "steam_games_reviews.csv")

# The "reviews" field is not JSON and does not contain per-user Steam
# reviews. It contains 0-10 concatenated critic/press pull-quotes in the
# form: "<curly-quote>text<curly-quote> score - outlet". This regex
# recovers (quote_text, trailing_attribution) pairs.
QUOTE_PATTERN = re.compile(r"“(.*?)”\s*([^“]*)")


def load_games(path: str = GAMES_PATH) -> pd.DataFrame:
    """Load steam_games.csv with light dtype tightening to reduce memory."""
    df = pd.read_csv(path, low_memory=False)
    for col in ["price_status"]:
        if col in df.columns:
            df[col] = df[col].astype("category")
    return df


def load_reviews(path: str = REVIEWS_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def parse_list_field(s):
    """Normalize genres/categories/tags/developers/publishers into a list of strings.

    Two serializations were found empirically for genres/categories:
      - plain string lists:  ["Action", "Adventure"]
      - Steam-API dict lists: [{"id": "4", "description": "Casual"}]
    Both are normalized to a flat list of strings. Returns None if the
    value cannot be parsed at all (distinct from an intentional empty list).
    """
    if pd.isna(s):
        return None
    s = str(s).strip()
    if s in ("", "[]"):
        return []
    try:
        v = json.loads(s)
    except Exception:
        try:
            v = ast.literal_eval(s)
        except Exception:
            return None
    if not isinstance(v, list):
        return None
    if v and isinstance(v[0], dict):
        return [item.get("description", str(item)) for item in v if isinstance(item, dict)]
    return v


def parse_tags_field(s):
    """Parse the 'tags' column specifically.

    Discovered in Phase 5: tags have a THIRD serialization format beyond the two
    parse_list_field handles -- a JSON object mapping tag name to community vote
    count, e.g. {"Farming Sim": 7935, "Pixel Graphics": 7389, ...} (16.4% of the
    catalog, 22,806 rows -- including well-known, heavily-tagged titles such as
    Stardew Valley). parse_list_field silently returns None for this format since
    it isn't a list, which was undercounting real tag coverage. genres/categories
    were checked and confirmed NOT to have this dict format -- this fix is tags-only
    and does not change parse_list_field's behavior for any other column.

    Returns a list of tag names ordered by descending vote count for the dict
    format (vote counts themselves are discarded -- this returns tag *presence*,
    consistent with how the list-format tags are used elsewhere, not a popularity
    signal). Falls back to parse_list_field's list-format handling otherwise.
    """
    if pd.isna(s):
        return None
    s = str(s).strip()
    if s in ("", "[]", "{}"):
        return []
    try:
        v = json.loads(s)
    except Exception:
        try:
            v = ast.literal_eval(s)
        except Exception:
            return None
    if isinstance(v, dict):
        return [k for k, _ in sorted(v.items(), key=lambda kv: -kv[1])]
    return parse_list_field(s)


def estimated_owners_format(s) -> str:
    """Two delimiter/format conventions were found for estimated_owners:
    '0 - 20000' and '0 .. 20,000'. Returns 'dash', 'dotdot', 'null' or 'other'.
    """
    if pd.isna(s):
        return "null"
    s = str(s)
    if ".." in s:
        return "dotdot"
    if "-" in s:
        return "dash"
    return "other"


def parse_estimated_owners(s):
    """Parse an estimated_owners range string (either format) into (lo, hi, mid).

    This is an AUDIT-time convenience parse for inspecting the field's
    granularity -- it is not a final modeling representation.
    """
    if pd.isna(s):
        return (np.nan, np.nan, np.nan)
    digits = re.findall(r"[\d,]+", str(s))
    if len(digits) < 2:
        return (np.nan, np.nan, np.nan)
    lo = int(digits[0].replace(",", ""))
    hi = int(digits[1].replace(",", ""))
    return (lo, hi, (lo + hi) / 2)


def parse_review_quotes(s):
    """Parse the (non-standard) 'reviews' field into a list of
    (quote_text, attribution) tuples. Returns [] for '[]'/empty/NaN.
    """
    if pd.isna(s):
        return []
    s = str(s).strip()
    if s in ("", "[]"):
        return []
    return QUOTE_PATTERN.findall(s)


def attribution_to_outlet(attr: str) -> str:
    """Best-effort extraction of the outlet/attributor name from a
    'score - outlet' style attribution string."""
    parts = re.split(r"[-–—]", attr)
    return parts[-1].strip() if parts else attr.strip()


def top_items(series_of_lists, n=20) -> list:
    c = Counter()
    for v in series_of_lists:
        if isinstance(v, list):
            for item in v:
                c[item] += 1
    return c.most_common(n)
