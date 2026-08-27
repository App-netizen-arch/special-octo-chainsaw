"""PII detection & redaction primitives (shared by logging and verification).

Strategy: deterministic regexes first (emails, phones, IDs, addresses),
then optional spaCy NER for person/org names when the model is installed —
the module degrades gracefully to heuristics without spaCy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------- patterns

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3}[\s.-]?\d{3,4}(?:[\s.-]?\d{2,4})?"
)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
CASE_NO_RE = re.compile(
    r"\b(?:Case\s+(?:No\.?|Number)[:\s]*|[Dd]ocket\s*(?:No\.?|)[:]?\s*)[A-Z]{0,3}[-:\s]*\d{2,}[-–/]?[A-Za-z0-9]*\b"
)
STREET_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z.]+\s(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b\.?"
)

_NAME_HINT_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Hon|Adv)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
)
_CAP_NAME_RE = re.compile(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b")

_SPACY_CACHE: dict[str, object] = {"model": None, "tried": False}


def _spacy_ner():
    """Return a loaded spaCy pipeline or None (cached)."""
    if _SPACY_CACHE["tried"]:
        return _SPACY_CACHE["model"]
    _SPACY_CACHE["tried"] = True
    try:
        import spacy  # type: ignore

        try:
            nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
        except OSError:
            return None
        _SPACY_CACHE["model"] = nlp
        return nlp
    except ImportError:
        return None


@dataclass
class PiiFinding:
    kind: str  # email|phone|ssn|iban|case_number|address|person_name
    value: str
    start: int
    end: int


@dataclass
class PiiReport:
    findings: list[PiiFinding] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return bool(self.findings)

    @property
    def kinds(self) -> list[str]:
        return sorted({f.kind for f in self.findings})

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.kind] = counts.get(f.kind, 0) + 1
        return {"has_pii": self.has_pii, "counts": counts}


# --------------------------------------------------------------- detection


def detect(text: str, include_names: bool = True) -> list[PiiFinding]:
    """Return all PII findings in `text` (values included; callers must not log them raw)."""
    findings: list[PiiFinding] = []
    spans: set[tuple[int, int]] = set()

    def add(kind: str, match: re.Match) -> None:
        s, e = match.span()
        if (s, e) in spans or not match.group(0).strip():
            return
        # phone heuristic: require >=7 digits total to avoid matching years etc.
        if kind == "phone":
            digits = sum(c.isdigit() for c in match.group(0))
            if digits < 7 or digits > 15:
                return
        if kind == "address" and any((s2, e2) in spans for s2, e2 in [(s, e)]):
            return
        spans.add((s, e))
        findings.append(PiiFinding(kind=kind, value=match.group(0), start=s, end=e))

    for pattern, kind in (
        (SSN_RE, "ssn"),
        (IBAN_RE, "iban"),
        (EMAIL_RE, "email"),
        (CASE_NO_RE, "case_number"),
        (STREET_RE, "address"),
        (PHONE_RE, "phone"),
    ):
        for m in pattern.finditer(text):
            add(kind, m)

    if include_names:
        nlp = _spacy_ner()
        if nlp is not None:
            doc = nlp(text[:20000])
            for ent in doc.ents:
                if ent.label_ == "PERSON" and len(ent.text.split()) <= 4:
                    findings.append(
                        PiiFinding("person_name", ent.text, ent.start_char, ent.end_char)
                    )
        else:
            for m in _NAME_HINT_RE.finditer(text):
                findings.append(
                    PiiFinding("person_name", m.group(0), m.start(), m.end())
                )
            for m in _CAP_NAME_RE.finditer(text):
                candidate = m.group(0)
                # skip obvious legal boilerplate / orgs
                if any(
                    w in candidate
                    for w in ("Court", "Party", "Agreement", "United States", "Non Disclos")
                ):
                    continue
                findings.append(PiiFinding("person_name", candidate, m.start(), m.end()))

    findings.sort(key=lambda f: f.start)
    return findings


# --------------------------------------------------------------- redaction


def redact_text(text: str) -> str:
    """Replace PII with typed placeholders. Used for logs and exports."""
    text = SSN_RE.sub("[REDACTED-SSN]", text)
    text = IBAN_RE.sub("[REDACTED-IBAN]", text)
    text = EMAIL_RE.sub("[REDACTED-EMAIL]", text)
    text = CASE_NO_RE.sub("[REDACTED-CASENO]", text)
    text = STREET_RE.sub("[REDACTED-ADDRESS]", text)
    text = PHONE_RE.sub(_redact_phone, text)

    nlp = _spacy_ner()
    if nlp is not None:
        doc = nlp(text[:20000])
        out = text
        offset = 0
        for ent in doc.ents:
            if ent.label_ != "PERSON" or len(ent.text.split()) > 4:
                continue
            s, e = ent.start_char + offset, ent.end_char + offset
            out = out[:s] + "[REDACTED-NAME]" + out[e:]
            offset += len("[REDACTED-NAME]") - (e - s)
        return out
    return _NAME_HINT_RE.sub(lambda m: m.group(0).split()[0] + " [REDACTED-NAME]", text)


def _redact_phone(match: re.Match) -> str:
    digits = sum(c.isdigit() for c in match.group(0))
    return "[REDACTED-PHONE]" if 7 <= digits <= 15 else match.group(0)
