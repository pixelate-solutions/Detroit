"""CPU-only demo provider used when Ollama is not installed.

Nothing here is a language model. It exists so the full pipeline (ingest -> chunk ->
embed -> ChromaDB -> retrieval -> cited answer) can be demonstrated on any laptop:

* embeddings: deterministic feature-hashed bag of words and bigrams (384 dims, L2-normalised)
* answers: extractive. The highest-scoring sentences from the retrieved passages are
  quoted verbatim with [C#] citation markers, so every claim is traceable to a source page
* graph extraction: regular expressions for case numbers, addresses, organisations, people
* comparisons: a structured summary of added and removed lines
"""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterator

DIMENSIONS = 384
STOPWORDS = set(
    """a an and are as at be been but by can did do does for from had has have how i if in into is it its
    of on or our so that the their them then there these they this to was we were what when where which
    who why will with you your any all about after before current currently there's what's""".split()
)
TOKEN = re.compile(r"[a-z0-9][a-z0-9\-']*")


def _tokens(text: str) -> list[str]:
    words = [word.strip("'-") for word in TOKEN.findall(text.lower())]
    return [_stem(word) for word in words if word and word not in STOPWORDS]


def _stem(word: str) -> str:
    for suffix in ("ings", "ing", "ies", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            word = word[: -len(suffix)] + ("y" if suffix == "ies" else "")
            break
    return word[:-1] if len(word) > 4 and word.endswith("e") else word


def _bucket(feature: str) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    return value % DIMENSIONS, 1.0 if (value >> 63) & 1 else -1.0


def embed(texts: list[str]) -> list[list[float]]:
    vectors = []
    for text in texts:
        vector = [0.0] * DIMENSIONS
        tokens = _tokens(text)
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for feature in features:
            index, sign = _bucket(feature)
            vector[index] += sign * (1.5 if "_" in feature else 1.0)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        vectors.append([value / norm for value in vector])
    return vectors


# --------------------------------------------------------------------------- answers

SENTENCE = re.compile(r"(?<=[a-z0-9)][.!?])\s+(?=[A-Z0-9\"'(])")
LABEL = re.compile(r"^[A-Z][A-Za-z' ]{1,28}:\s")
FIELD_LINE = re.compile(r"^[A-Z][A-Za-z' ]{1,28}:\s.{0,90}$")


def _sentences(text: str) -> list[str]:
    """Split a chunk into sentences, rejoining lines that PDF extraction wrapped mid-sentence."""
    blocks: list[str] = []
    current: list[str] = []
    for raw in text.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            if current:
                blocks.append(" ".join(current))
                current = []
            continue
        # A "Field: value" line or an all-caps heading stands alone; prose lines are joined.
        if FIELD_LINE.match(line) or (line.isupper() and len(line) < 90):
            if current:
                blocks.append(" ".join(current))
                current = []
            blocks.append(line)
            continue
        current.append(line)
    if current:
        blocks.append(" ".join(current))
    parts: list[str] = []
    for block in blocks:
        parts.extend(piece.strip() for piece in SENTENCE.split(block) if piece.strip())
    return parts


def select_evidence(question: str, results: list[dict], limit: int = 5) -> list[tuple[int, str, float]]:
    """Return (citation_number, sentence, score) for the best sentences across results.

    Query terms are weighted by inverse frequency across the retrieved sentences, so a
    term every passage shares (an address, the department name) counts for little and
    the discriminating words in the question decide the ranking.
    """
    query_terms = set(_tokens(question))
    candidates: list[tuple[int, int, str, set[str]]] = []
    for number, item in enumerate(results, start=1):
        for position, sentence in enumerate(_sentences(item.get("text") or item["snippet"])):
            if len(sentence) < 25 or sentence.isupper():
                continue
            candidates.append((number, position, sentence, set(_tokens(sentence))))
    if not candidates:
        return []
    total = len(candidates)
    weights = {
        term: math.log(1 + total / (1 + sum(1 for c in candidates if term in c[3]))) for term in query_terms
    }
    scored: list[tuple[float, int, str]] = []
    for number, _position, sentence, terms in candidates:
        overlap = terms & query_terms
        if not overlap:
            continue
        score = sum(weights[term] for term in overlap) / math.sqrt(len(terms) + 6)
        if LABEL.match(sentence) and len(sentence) < 100:
            score *= 0.55
        if re.search(r"\d", sentence):
            score *= 1.1
        score *= 1.0 / (1.0 + 0.08 * (number - 1))
        scored.append((score, number, sentence))
    scored.sort(key=lambda value: value[0], reverse=True)

    picked: list[tuple[int, str, float]] = []
    seen: set[str] = set()
    # First pass: the best sentence from each record, for breadth. Second pass: fill.
    for max_per_source in (1, 2):
        per_source: dict[int, int] = {n: sum(1 for p in picked if p[0] == n) for n, _, _ in picked}
        for score, number, sentence in scored:
            if len(picked) >= limit:
                break
            key = sentence.lower()[:80]
            if key in seen or per_source.get(number, 0) >= max_per_source:
                continue
            if picked and score < picked[0][2] * 0.3:
                continue
            seen.add(key)
            per_source[number] = per_source.get(number, 0) + 1
            picked.append((number, sentence, score))
    return picked


def answer(question: str, results: list[dict]) -> str:
    evidence = select_evidence(question, results)
    if not evidence:
        return (
            "The records available to your role do not contain a passage that answers this question. "
            "Try different wording, or ask a records administrator whether a restricted record applies."
        )
    lead_number, lead_sentence, _ = evidence[0]
    lines = [
        "**Most relevant finding**",
        "",
        f"> {lead_sentence} [C{lead_number}]",
        "",
    ]
    if len(evidence) > 1:
        lines += ["**Supporting record excerpts**", ""]
        for number, sentence, _ in evidence[1:]:
            title = results[number - 1]["title"]
            lines.append(f"- *{title}*: \"{sentence}\" [C{number}]")
        lines.append("")
    lines.append(
        "_Demo mode: this answer is extractive. Sentences are quoted verbatim from the cited records "
        "by a keyword-and-vector ranker; no language model was used. Connect a local Ollama model "
        "for synthesized answers._"
    )
    return "\n".join(lines)


def analysis(question: str, results: list[dict]) -> str:
    documents = []
    for item in results:
        if item["title"] not in documents:
            documents.append(item["title"])
    evidence = select_evidence(question, results, limit=3)
    cited = ", ".join(f"[C{number}]" for number, _, _ in evidence) or "none"
    return (
        f"I ranked {len(results)} passages from {len(documents)} records you are cleared to read. "
        f"The strongest matches come from {', '.join(documents[:3])}. "
        f"Passages quoted in the answer: {cited}."
    )


def stream_words(text: str) -> Iterator[str]:
    for piece in re.findall(r"\S+\s*|\n", text):
        yield piece


# --------------------------------------------------------------------------- graph

CASE = re.compile(r"\b(?:[A-Z]{2,4}-\d{2,4}-\d{2,4}|SOP\s\d{3}|PIP-\d{4}|H-\d-\d{3})\b")
INCIDENT = re.compile(r"\b(?:Incident(?: Report)?\s)(\d{2}-\d{5})\b")
ADDRESS = re.compile(
    r"\b\d{2,5}\s(?:[A-Z][a-z]+\s){1,3}(?:Street|Avenue|Road|Lane|Drive|Boulevard|Parkway|Way|Court)\b"
)
ORG = re.compile(
    r"\b(?:[A-Z][A-Za-z&]+\s){1,4}(?:LLC|Inc\.?|Cooperative|Company|Corporation|Partners|Station \d+|Engine \d+|Ladder \d+)\b"
)
PERSON_LABEL = re.compile(
    r"(?:Inspector|Captain|Lieutenant|Chief|Battalion Chief|Fire Marshal|Engineer|Firefighter|Officer|Manager|"
    r"Prepared by|Reviewed by|Approved by|Investigator|Tested by|Employee|Reporting officer)[:\s]+(?:(?:Lt|Capt|FF)\.\s)?"
    r"((?:[A-Z][a-z]+\s)?[A-Z][a-z]+\s[A-Z][a-z'\-]+)"
)


def extract_graph(title: str, text: str) -> dict:
    entities: dict[str, dict] = {}

    def add(name: str, kind: str, observation: str) -> None:
        name = " ".join(name.split()).rstrip(".,")
        if len(name) < 4:
            return
        entity = entities.setdefault(name, {"name": name, "entityType": kind, "observations": []})
        if observation not in entity["observations"]:
            entity["observations"].append(observation)

    for match in CASE.finditer(text):
        add(match.group(0), "case_number", f"Referenced in {title}")
    for match in INCIDENT.finditer(text):
        add(f"Incident {match.group(1)}", "case_number", f"Referenced in {title}")
    for match in ADDRESS.finditer(text):
        add(match.group(0), "address", f"Location in {title}")
    for match in ORG.finditer(text):
        add(match.group(0), "organization", f"Named in {title}")
    for match in PERSON_LABEL.finditer(text):
        add(match.group(1), "person", f"Named in {title}")

    names = list(entities)
    relations = []
    anchors = [name for name in names if entities[name]["entityType"] in {"case_number", "address"}]
    for anchor in anchors[:3]:
        for other in names:
            if other != anchor:
                relations.append({"from": anchor, "to": other, "relationType": "appears_with"})
    return {"entities": list(entities.values()), "relations": relations[:60]}


# --------------------------------------------------------------------------- compare

def compare_summary(before: dict, after: dict) -> str:
    """Sentence-level diff: pair each revised sentence with the one it replaced."""
    import difflib

    def sentences(text: str) -> list[str]:
        return [item for item in _sentences(text) if not item.isupper() and len(item) > 20]

    old, new = sentences(before["full_text"]), sentences(after["full_text"])
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    changes: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            for was, now in zip(old[i1:i2], new[j1:j2]):
                changes.append(f"- **Now:** {now}\n  **Was:** ~~{was}~~")
            for now in new[j1 + (i2 - i1):j2]:
                changes.append(f"- **Added:** {now}")
        elif tag == "insert":
            changes += [f"- **Added:** {now}" for now in new[j1:j2]]
        elif tag == "delete":
            changes += [f"- **Removed:** ~~{was}~~" for was in old[i1:i2]]
    if not changes:
        return "The two records contain the same text."
    lines = [f"**{len(changes)} sentences changed** from *{before['title']}* to *{after['title']}*.", "", *changes[:7]]
    lines += ["", "_Demo mode: a deterministic sentence-level diff. With a local LLM, this panel explains the operational impact._"]
    return "\n".join(lines)
