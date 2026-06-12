from __future__ import annotations

import re
from dataclasses import dataclass

from asktrainmind.app.excel_model import FunctionRecord

STOPWORDS = {
    "come",
    "funziona",
    "il",
    "la",
    "lo",
    "gli",
    "le",
    "e",
    "di",
    "a",
    "da",
    "del",
    "della",
    "delle",
    "dei",
    "for",
    "the",
    "how",
    "does",
    "work",
    "component",
    "componente",
    "please",
}
COMPONENT_RE = re.compile(r"\b[A-Za-z]{1,5}-[A-Za-z0-9]{2,}\b")
DOC_ID_RE = re.compile(r"\b[A-Za-z]{1,8}_[A-Za-z0-9]{1,}\b")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{2,}")


@dataclass
class MatchResult:
    record: FunctionRecord
    score: int
    matched_terms: list[str]


def extract_keywords(question: str) -> set[str]:
    tokens = {m.group(0).upper() for m in COMPONENT_RE.finditer(question)}
    tokens.update({m.group(0).upper() for m in DOC_ID_RE.finditer(question)})
    for token in TOKEN_RE.findall(question):
        lower = token.lower()
        if lower not in STOPWORDS and len(token) >= 2:
            tokens.add(token.upper())
    return tokens


def _record_text(record: FunctionRecord) -> str:
    parts = [record.id, record.funzione, record.tipo]
    for doc in record.documents:
        parts.extend([doc.doc_id, doc.info_doc])
        parts.extend(doc.config_links.values())
        for detail in doc.details:
            parts.append(detail.title)
            parts.extend(detail.values.values())
    return "\n".join(parts).upper()


def rank_function_records(question: str, records: list[FunctionRecord], limit: int = 20) -> list[MatchResult]:
    keywords = extract_keywords(question)
    if not keywords:
        return []

    matches: list[MatchResult] = []
    for record in records:
        blob = _record_text(record)
        found = sorted([kw for kw in keywords if kw in blob])
        if found:
            score = sum(3 if kw in {record.id.upper(), record.funzione.upper()} else 1 for kw in found)
            matches.append(MatchResult(record=record, score=score, matched_terms=found))

    return sorted(matches, key=lambda item: (-item.score, item.record.id))[:limit]
