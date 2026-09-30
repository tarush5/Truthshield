"""
What a claim is actually about.

Retrieval quality is the measured bottleneck in this system -- the benchmark
fixture's three abstentions are all caused by evidence that never addressed
the claim -- and the cause was here, in how the reference-work query was
built.

The previous implementation took capitalised words as entities:

    entities = re.findall(r"\\b[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*\\b", text)
    if entities:
        return " ".join(entities[:4])

which matches the sentence-initial capital, because that is grammar rather
than a name. Measured across the fixture it produced:

    "Drinking bleach cures COVID-19 within 24 hours."  -> "Drinking"
    "Smoking tobacco causes lung cancer."              -> "Smoking"
    "Humans only use ten percent of their brains."     -> "Humans"
    "NASA confirmed the moon landing was filmed ..."   -> "Hollywood"
    "Vaccines cause autism according to a 2019 WHO ..."-> "Vaccines"

A Wikipedia search for "Humans" returns the Warcraft: Orcs & Humans page
and the IMDb entry for a television series; a search for "Vaccines" returns
the indie band. Both appeared verbatim in the retrieved evidence. The
bleach case is the clearest: the query for a claim about bleach and COVID
was the word "Drinking".

This module replaces that with three ranked signals, kept together rather
than first-four-wins:

  1. **Acronyms and alphanumerics** -- NASA, WHO, COVID-19, 5G. The highest
     signal per character in a claim, and the previous regex could not
     match them at all: `[A-Z][a-z]+` requires a lowercase tail.
  2. **Proper nouns**, counted only when capitalised *away* from a sentence
     start, so grammar is not mistaken for a name.
  3. **Distinctive content words**, so a claim with no names at all still
     produces a query about its subject rather than its first word.

No model is involved. This is the cheap fix that had to happen before any
model could help, because no amount of reranking rescues a result set
retrieved for the wrong subject.
"""

from __future__ import annotations

import re
from typing import List

# Enough to name a subject; past this, search engines weight the tail terms
# down to noise anyway.
MAX_TERMS = 6

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*|\d+[A-Za-z]+|[A-Z]{2,}(?:-\d+)?")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Acronyms, model numbers and disease names: NASA, WHO, COVID-19, 5G, H1N1.
_ACRONYM = re.compile(r"\b(?:[A-Z]{2,}(?:-?\d+)?|\d+[A-Z]{1,3})\b")

# Function words, plus the verbs claims are built from. "causes", "cures"
# and "spread" describe the *assertion*; they are not what it is about, and
# including them pulls in every article that makes any causal claim.
_STOP = frozenset("""
a an the this that these those there here it its it's is are was were be been
being am do does did doing have has had having will would shall should can
could may might must of in on at to for from by with about against between
into through during before after above below up down out off over under again
further then once and or but if because as until while not no nor only own
same so than too very just
i you he she we they me him her us them my your his their our
say says said claim claims claimed show shows showed prove proves proved
cause causes caused cure cures cured spread spreads make makes made use uses
used according within per
""".split())

# Kept even though short: they carry the subject.
_KEEP_SHORT = frozenset({"5g", "ai", "uv", "tv", "un", "us", "uk", "eu", "oil", "gas", "war"})


def _sentence_starts(text: str) -> set:
    """
    Words that open a sentence.

    These are capitalised by grammar, so a capital here proves nothing about
    whether the word is a name -- which is the assumption the old extractor
    was built on.
    """
    starts = set()
    for sentence in _SENTENCE_SPLIT.split(text.strip()):
        first = _WORD.search(sentence)
        if first:
            starts.add(first.group(0))
    return starts


def _acronyms(text: str) -> List[str]:
    out, seen = [], set()
    for match in _ACRONYM.finditer(text):
        token = match.group(0)
        # A fully capitalised sentence would otherwise read as all acronyms.
        if token.isalpha() and len(token) > 6:
            continue
        if token.lower() not in seen:
            seen.add(token.lower())
            out.append(token)
    return out


def _proper_nouns(text: str, starts: set) -> List[str]:
    """
    Capitalised runs that are not merely sentence-initial.

    A word that opens a sentence is only accepted when it also appears
    capitalised elsewhere in the text -- which is what distinguishes a real
    name from the first word of an English sentence.
    """
    out, seen = [], set()
    for match in re.finditer(r"\b[A-Z][a-z]+(?:\s+(?:of\s+)?[A-Z][a-z]+)*\b", text):
        phrase = match.group(0)
        head = phrase.split()[0]

        if head in starts and len(phrase.split()) == 1:
            # Sentence-initial and single-word: accept only if the same word
            # is capitalised somewhere it is not opening a sentence.
            elsewhere = [
                m.start() for m in re.finditer(rf"\b{re.escape(head)}\b", text)
            ]
            if len(elsewhere) < 2:
                continue

        key = phrase.lower()
        if key not in seen and key not in _STOP:
            seen.add(key)
            out.append(phrase)
    return out


def _content_words(text: str, taken: set) -> List[str]:
    """
    What the claim is about, when it names nothing.

    Ordered by length as a crude proxy for specificity: "brains" outranks
    "use", and a query built from the longer terms lands closer to the
    subject than one built from the first words in the sentence.
    """
    scored = []
    for token in _WORD.findall(text):
        word = token.lower().strip("'-")
        if word in _STOP or word in taken:
            continue
        if len(word) < 4 and word not in _KEEP_SHORT:
            continue
        if word not in [w for w, _ in scored]:
            scored.append((word, len(word)))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [word for word, _ in scored]


def focus_terms(text: str, *, limit: int = MAX_TERMS) -> List[str]:
    """
    The terms a claim is about, most distinctive first.

    Acronyms, then proper nouns, then content words -- concatenated rather
    than falling through, so a claim containing one name does not lose its
    subject to that name.
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    starts = _sentence_starts(text)

    terms: List[str] = []
    seen = set()

    for source in (_acronyms(text), _proper_nouns(text, starts)):
        for term in source:
            key = term.lower()
            if key not in seen:
                seen.add(key)
                terms.append(term)

    # Every word already claimed by a phrase above, so "Great Wall" does not
    # come back as "great" and "wall".
    taken = {w for term in terms for w in term.lower().split()}
    for word in _content_words(text, taken):
        if word not in seen:
            seen.add(word)
            terms.append(word)

    return terms[:limit]


def entity_query(text: str, *, limit: int = 4) -> str:
    """
    A reference-work query (Wikipedia, Wikidata).

    Kept shorter than the web-search query: these are title-matched
    corpora, where extra terms cost recall rather than buying precision.
    """
    return " ".join(focus_terms(text, limit=limit))


def search_query(text: str, *, limit: int = MAX_TERMS) -> str:
    """A general web-search query for the same claim."""
    return " ".join(focus_terms(text, limit=limit))
