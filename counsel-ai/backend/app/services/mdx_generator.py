"""MDX document generation for legal templates.

The backend emits MDX-flavored Markdown (a frontmatter block plus standard
sections) that the Flutter renderer styles as a legal document. Template
skeletons follow conventional legal drafting structure; the LLM fills them
section-by-section at runtime.

Every generated document ends with the mandatory disclaimer footer:
"This tool assists drafting and research; it is not a substitute for
professional legal judgment."
"""

from __future__ import annotations

from datetime import date
from typing import Any

DISCLAIMER = (
    "This tool assists drafting and research; it is not a substitute "
    "for professional legal judgment."
)

TEMPLATES: dict[str, dict[str, Any]] = {
    "nda": {
        "label": "Non-Disclosure Agreement (NDA)",
        "doc_type": "nda",
        "skeleton": """export const frontmatter = {{
  type: "NDA",
  jurisdiction: "{jurisdiction}",
  status: "DRAFT — for review only"
}}

# MUTUAL NON-DISCLOSURE AGREEMENT

This Non-Disclosure Agreement ("Agreement") is entered into as of {today}, between:

**Party A:** ______________________________ ("Disclosing Party"), and

**Party B:** ______________________________ ("Receiving Party"),

each a "Party" and together the "Parties".

## 1. Purpose

The Parties wish to explore a business relationship (the "Purpose") and may disclose confidential information to each other in connection with the Purpose.

## 2. Confidential Information

"Confidential Information" means any non-public information disclosed by either Party, whether oral, written or electronic, that is designated confidential or that reasonably should be understood to be confidential given its nature.

## 3. Obligations of the Receiving Party

The Receiving Party shall: (a) use the Confidential Information solely for the Purpose; (b) not disclose it to third parties without prior written consent; (c) protect it with at least the same degree of care it uses for its own confidential information.

## 4. Exclusions

Confidential Information does not include information that is or becomes public through no fault of the Receiving Party, was rightfully known prior to disclosure, is independently developed, or is rightfully received from a third party.

## 5. Term and Termination

This Agreement commences on the Effective Date and continues for ______ years unless terminated earlier by either Party upon written notice.

## 6. Governing Law

This Agreement is governed by the laws of {jurisdiction}, without regard to conflict-of-law rules.

## Signatures

| | Party A | Party B |
|---|---------|---------|
| Signature | ______________ | ______________ |
| Name | ______________ | ______________ |
| Date | ______________ | ______________ |

---
*Drafted with Counsel AI. {disclaimer} This draft must be reviewed by a qualified lawyer before use.*
""",
    },
    "employment_contract": {
        "label": "Employment Contract",
        "doc_type": "employment_contract",
        "skeleton": """export const frontmatter = {{
  type: "Employment Contract",
  jurisdiction: "{jurisdiction}",
  status: "DRAFT — for review only"
}}

# EMPLOYMENT CONTRACT

This Employment Contract ("Contract") is made on {today} between:

**Employer:** ______________________________ , and

**Employee:** ______________________________ .

## 1. Position and Duties

The Employee is engaged as ______________________ and shall perform duties reasonably associated with that role.

## 2. Commencement

Employment begins on ____________ and continues until terminated under this Contract.

## 3. Remuneration

The Employer shall pay the Employee a salary of ____________ per ______, subject to lawful deductions.

## 4. Working Hours

Standard working hours are ______ per week, consistent with applicable working-time legislation in {jurisdiction}.

## 5. Leave

The Employee is entitled to statutory annual leave and public holidays in accordance with {jurisdiction} law.

## 6. Confidentiality

The Employee shall not, during or after employment, disclose confidential information belonging to the Employer.

## 7. Termination

Either Party may terminate this Contract by giving ______ weeks' written notice.

## 8. Governing Law

This Contract is governed by the laws of {jurisdiction}.

## Signatures

| | Employer | Employee |
|---|----------|----------|
| Signature | ______________ | ______________ |
| Date | ______________ | ______________ |

---
*Drafted with Counsel AI. {disclaimer}*
""",
    },
    "legal_memo": {
        "label": "Legal Memo",
        "doc_type": "legal_memo",
        "skeleton": """export const frontmatter = {{
  type: "Legal Memorandum",
  jurisdiction: "{jurisdiction}",
  status: "DRAFT — privileged & confidential"
}}

# LEGAL MEMORANDUM

**To:** ______________________
**From:** ______________________
**Date:** {today}
**Re:** ______________________

## Question Presented

<State the precise legal question.>

## Brief Answer

<One-paragraph answer.>

## Facts

<Concise statement of material facts.>

## Discussion

<Apply governing law from {jurisdiction} to the facts, citing authorities.>

## Conclusion & Recommendations

<Actionable recommendations.>

---
*Privileged and confidential. Prepared with Counsel AI for internal review. {disclaimer}*
""",
    },
    "motion": {
        "label": "Court Motion",
        "doc_type": "motion",
        "skeleton": """export const frontmatter = {{
  type: "Motion",
  jurisdiction: "{jurisdiction}",
  status: "DRAFT — filing rules must be verified"
}}

# MOTION FOR ______________________

**In the matter of:** ______________________
**Case No.:** ______________________
**Court:** ______________________ ({jurisdiction})

## I. Introduction

Plaintiff/Defendant respectfully moves this Honourable Court for an order ______________________.

## II. Background

<Brief procedural history.>

## III. Argument

<Point I — standard. Point II — application to facts, with citations.>

## IV. Relief Requested

For the foregoing reasons, the Movant requests that the Court: 1) grant the instant motion; 2) grant such further relief as just.

Respectfully submitted,

______________________
Counsel for Movant
{today}

---
*Drafted with Counsel AI. {disclaimer}*
""",
    },
    "letter": {
        "label": "Formal Letter",
        "doc_type": "letter",
        "skeleton": """export const frontmatter = {{
  type: "Letter",
  jurisdiction: "{jurisdiction}",
  status: "DRAFT — for review only"
}}

[Firm Letterhead]

{today}

**Via Email & Registered Post**

Recipient Name
Recipient Address

**Re: ______________________**

Dear ______________,

<Body paragraphs: instruction, position, demand/next step, deadline.>

Yours faithfully,

______________________
Name
Title
Enclosures: ___
cc: ___

---
*Drafted with Counsel AI. {disclaimer}*
""",
    },
}


def render_skeleton(template_key: str, jurisdiction: str) -> str:
    tpl = TEMPLATES[template_key]["skeleton"]
    return tpl.format(
        jurisdiction=jurisdiction or "the applicable jurisdiction",
        today=date.today().isoformat(),
        disclaimer=DISCLAIMER,
    )


def template_labels() -> dict[str, str]:
    return {k: v["label"] for k, v in TEMPLATES.items()}


def mdx_document_prompt(instruction: str, template_key: str | None,
                        jurisdiction: str, skill_blocks: list[str] | None = None) -> str:
    """Instruction wrapper telling the LLM to answer in MDX document form."""
    base = (
        "Draft a complete legal document as MDX (Markdown with a small code "
        "frontmatter block at the very top starting with 'export const "
        "frontmatter'). Use clear numbered headings (## 1., ## 2.), signature "
        "tables where appropriate, and placeholder underscores for unknown "
        "facts. End with an italic disclaimer containing exactly this sentence: "
        f"'{DISCLAIMER}' Jurisdiction: {jurisdiction}. "
        f"Today's date: {date.today().isoformat()}. Instruction:\n\n{instruction}"
    )
    if skill_blocks:
        base += "\n\nFollow these active skills:\n- " + "\n- ".join(skill_blocks)
    if template_key and template_key in TEMPLATES:
        base += f"\n\nBase the structure on the '{TEMPLATES[template_key]['label']}' template."
    return base
