"""Symbolic verification layer for legal outputs.

Deterministic, non-LLM checks that every generated document passes through:

* ``citation_validator``  — Bluebook/OSCOLA format validation of citations.
* ``source_existence``    — HTTP existence + quote-match verification.
* ``clause_rules``        — required-sections rule engine per document type.
* ``pii_detector``        — PII scan (regex + optional spaCy NER).
* ``jurisdiction_checker``— jurisdiction reference consistency.

``orchestrator.verify_document`` runs the full battery and returns a single
JSON report consumed by the Reviewer Agent and the Flutter UI. Chat/research
flows use the lightweight subset (source existence + PII).
"""
