"""
Evaluation-set hygiene: near-duplicate detection and leakage-free splits.

Two problems this exists to catch:

* **Leakage.** A test item that is a light rewording of a development item
  measures memory, not generalisation. Items are compared on word 3-gram
  shingles (Jaccard similarity), which catches template variants such as
  the same scam with a different bank name or amount.
* **Split drift.** When labelled examples arrive over time (reviewer
  decisions), each must land in the same split forever, and near-duplicate
  variants must land together. `assign_split` hashes the item's *group key*
  (its normalised template), so the assignment is stable and a campaign's
  variants cannot straddle development and test.
"""

from __future__ import annotations

import hashlib
import json
import re
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
# Numbers, amounts, links and handles vary between copies of one template.
_VOLATILE = re.compile(r"https?://\S+|\S+@\S+|\d[\d,./:-]*")

NEAR_DUPLICATE = 0.6


def template(text: str) -> str:
    """Lower-cased words with numbers, links and addresses blanked."""
    return " ".join(_WORD.findall(_VOLATILE.sub(" ", (text or "").lower())))


def shingles(text: str, n: int = 3) -> set:
    words = template(text).split()
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def load_sets(folder: Path, pattern: str = "fraud_*.jsonl") -> Dict[str, List[dict]]:
    out = {}
    for path in sorted(folder.glob(pattern)):
        with path.open(encoding="utf-8") as fh:
            out[path.stem] = [json.loads(line) for line in fh if line.strip()]
    return out


def near_duplicates(sets: Dict[str, List[dict]], threshold: float = NEAR_DUPLICATE,
                    only_between: Iterable[str] = ()) -> List[Tuple[float, str, str, str, str]]:
    """(similarity, set_a, id_a, set_b, id_b) for every pair at or above `threshold` across sets."""
    focus = set(only_between)
    items = [(name, item["id"], shingles(item["content"])) for name, rows in sets.items() for item in rows]
    found = []
    for (sa, ia, ha), (sb, ib, hb) in combinations(items, 2):
        if sa == sb or (focus and sa not in focus and sb not in focus):
            continue
        sim = jaccard(ha, hb)
        if sim >= threshold:
            found.append((round(sim, 3), sa, ia, sb, ib))
    return sorted(found, reverse=True)


def assign_split(text: str, *, validation: float = 0.15, test: float = 0.15) -> str:
    """Stable split for a labelled item, keyed on its template so variants travel together."""
    bucket = int(hashlib.sha256(template(text).encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    if bucket < test:
        return "test"
    if bucket < test + validation:
        return "validation"
    return "development"
