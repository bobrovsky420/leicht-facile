"""What the model answers with, parsed leniently.

An 8B model gets details wrong that do not matter: "s4" instead of "s0004", a kind
in capitals, one string where a list was asked for. These models accept such answers
and normalise them; the stages then turn them into the strict artifacts of
`leichtfacile.schemas`. Anything that does matter (a missing text, no blocks at all)
still fails validation, and the error goes back to the model once (llm/json_out.py).
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_DOT_LIKE = "\u2022\u2219\u22c5\u2027\u0387\u30fb\uff65"
_MEDIOPUNKT_RE = re.compile(r"(?<=[^\W\d_])[" + _DOT_LIKE + r"](?=[^\W\d_])")


def clean_text(text: str) -> str:
    """Whitespace collapsed, Mediopunkt look-alikes replaced by the Mediopunkt."""
    text = _MEDIOPUNKT_RE.sub("·", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_id(raw: Any, prefix: str, width: int) -> str | None:
    """'s4', 'S0004', '4' -> 's0004' (prefix s, width 4)."""
    if raw is None:
        return None
    m = re.fullmatch(rf"\s*{prefix}?(\d+)(?:\.(\d+))?\s*", str(raw), re.IGNORECASE)
    if not m:
        return str(raw).strip()
    out = f"{prefix}{int(m.group(1)):0{width}d}"
    return f"{out}.{m.group(2)}" if m.group(2) else out


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        return [p for p in re.split(r"[,\s]+", value) if p] if "," in value else [value]
    return [value]


class LLMOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # The main list of the answer. A model that answers with just that list (seen in a
    # local run of the judge) is read as if it had wrapped it in an object.
    _list_field: ClassVar[str | None] = None

    @model_validator(mode="before")
    @classmethod
    def _wrap_bare_list(cls, data: Any) -> Any:
        if isinstance(data, list) and cls._list_field:
            return {cls._list_field: data}
        return data


def _segment_ids(value: Any) -> list[str]:
    return [i for i in (normalize_id(v, "s", 4) for v in _as_list(value)) if i]


def _fact_ids(value: Any) -> list[str]:
    return [i for i in (normalize_id(v, "f", 2) for v in _as_list(value)) if i]


def _block_ids(value: Any) -> list[str]:
    return [i for i in (normalize_id(v, "b", 3) for v in _as_list(value)) if i]


# -- understand ---------------------------------------------------------------------

FACT_KINDS = {
    "deadline", "amount", "obligation", "right", "condition", "contact", "procedure",
    "definition", "other",
}  # fmt: skip
_FACT_KIND_ALIASES = {
    "date": "deadline", "frist": "deadline", "termin": "deadline", "cost": "amount",
    "betrag": "amount", "fee": "amount", "duty": "obligation", "pflicht": "obligation",
    "recht": "right", "bedingung": "condition", "kontakt": "contact", "phone": "contact",
    "ablauf": "procedure", "begriff": "definition",
}  # fmt: skip


class RefOut(LLMOut):
    text: str | None = None
    segment_ids: list[str] = Field(default_factory=list)

    _ids = field_validator("segment_ids", mode="before")(_segment_ids)

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, v: Any) -> str | None:
        if v is None or (isinstance(v, str) and v.strip().lower() in ("", "null", "none", "-")):
            return None
        return clean_text(str(v))


class CoreOut(LLMOut):
    what: RefOut = Field(default_factory=RefOut)
    must_do: RefOut = Field(default_factory=RefOut)
    deadline: RefOut = Field(default_factory=RefOut)
    cost: RefOut = Field(default_factory=RefOut)
    contact: RefOut = Field(default_factory=RefOut)


class FactOut(LLMOut):
    id: str | None = None
    kind: str = "other"
    text: str
    value_norm: str | None = None
    segment_ids: list[str] = Field(default_factory=list)
    must_keep: bool = True

    _ids = field_validator("segment_ids", mode="before")(_segment_ids)

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, v: Any) -> str:
        kind = str(v or "other").strip().lower()
        kind = _FACT_KIND_ALIASES.get(kind, kind)
        return kind if kind in FACT_KINDS else "other"

    @field_validator("value_norm", mode="before")
    @classmethod
    def _value(cls, v: Any) -> str | None:
        if v is None:
            return None
        text = str(v).strip()
        return None if text.lower() in ("", "null", "none", "-") else text

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, v: Any) -> str:
        return clean_text(str(v))


class TermOut(LLMOut):
    term: str
    explanation: str
    segment_ids: list[str] = Field(default_factory=list)

    _ids = field_validator("segment_ids", mode="before")(_segment_ids)


class OmitOut(LLMOut):
    segment_ids: list[str] = Field(default_factory=list)
    reason: str = ""

    _ids = field_validator("segment_ids", mode="before")(_segment_ids)


class UnderstandOut(LLMOut):
    _list_field = "facts"

    doc_type: str = ""
    audience: str = ""
    core: CoreOut = Field(default_factory=CoreOut)
    facts: list[FactOut]  # required: a fragment of an answer must not pass as a fact sheet
    hard_terms: list[TermOut] = Field(default_factory=list)
    omit_candidates: list[OmitOut] = Field(default_factory=list)


# -- write ----------------------------------------------------------------------------

_BLOCK_KIND_ALIASES = {
    "heading": "heading", "title": "heading", "h1": "heading", "h2": "heading",
    "h3": "heading", "question": "heading", "überschrift": "heading",
    "list_item": "list_item", "list": "list_item", "item": "list_item",
    "bullet": "list_item", "listitem": "list_item", "aufzählung": "list_item",
}  # fmt: skip


class BlockOut(LLMOut):
    kind: str = "sentence"
    text: str
    fact_ids: list[str] = Field(default_factory=list)
    segment_ids: list[str] = Field(default_factory=list)

    _sids = field_validator("segment_ids", mode="before")(_segment_ids)
    _fids = field_validator("fact_ids", mode="before")(_fact_ids)

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, v: Any) -> str:
        return _BLOCK_KIND_ALIASES.get(str(v or "").strip().lower(), "sentence")

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, v: Any) -> str:
        text = clean_text(str(v))
        if not text:
            raise ValueError("empty block text")
        return re.sub(r"^(?:[-*\u2022]\s+|#+\s+)", "", text)  # Markdown leaks


class OmissionOut(LLMOut):
    what: str = ""
    why: str = ""
    segment_ids: list[str] = Field(default_factory=list)

    _ids = field_validator("segment_ids", mode="before")(_segment_ids)


class GlossaryOut(LLMOut):
    term: str
    explanation: str


class WriteOut(LLMOut):
    _list_field = "blocks"

    blocks: list[BlockOut]
    omissions: list[OmissionOut] = Field(default_factory=list)
    glossary: list[GlossaryOut] = Field(default_factory=list)

    @field_validator("blocks")
    @classmethod
    def _not_empty(cls, v: list[BlockOut]) -> list[BlockOut]:
        if not v:
            raise ValueError("the draft has no blocks")
        return v


# -- judge ----------------------------------------------------------------------------

_STATUS_ALIASES = {
    "present": "present", "ok": "present", "yes": "present", "vorhanden": "present",
    "missing": "missing", "absent": "missing", "fehlt": "missing", "no": "missing",
    "distorted": "distorted", "wrong": "distorted", "changed": "distorted",
    "falsch": "distorted", "verändert": "distorted",
}  # fmt: skip


class FactCheckOut(LLMOut):
    fact_id: str
    status: str
    block_ids: list[str] = Field(default_factory=list)
    note: str = ""

    _bids = field_validator("block_ids", mode="before")(_block_ids)

    @field_validator("fact_id", mode="before")
    @classmethod
    def _fid(cls, v: Any) -> str:
        return normalize_id(v, "f", 2) or str(v)

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, v: Any) -> str:
        status = _STATUS_ALIASES.get(str(v).strip().lower())
        if status is None:
            raise ValueError(f"unknown status {v!r}")
        return status


class UnsupportedOut(LLMOut):
    block_id: str
    note: str = ""

    @field_validator("block_id", mode="before")
    @classmethod
    def _bid(cls, v: Any) -> str:
        return normalize_id(v, "b", 3) or str(v)


class SemanticOut(LLMOut):
    block_id: str
    rule_id: str
    note: str = ""

    @field_validator("block_id", mode="before")
    @classmethod
    def _bid(cls, v: Any) -> str:
        return normalize_id(v, "b", 3) or str(v)

    @field_validator("rule_id", mode="before")
    @classmethod
    def _rid(cls, v: Any) -> str:
        m = re.search(r"(\d+)", str(v))
        return f"SEM-{int(m.group(1)):02d}" if m else str(v)


class JudgeOut(LLMOut):
    _list_field = "fact_checks"

    fact_checks: list[FactCheckOut]  # required: an empty report must be an explicit answer
    unsupported: list[UnsupportedOut] = Field(default_factory=list)
    semantic_findings: list[SemanticOut] = Field(default_factory=list)


# -- repair ---------------------------------------------------------------------------


class RepairItem(LLMOut):
    id: str
    texts: list[str]

    @field_validator("id", mode="before")
    @classmethod
    def _bid(cls, v: Any) -> str:
        return normalize_id(v, "b", 3) or str(v)

    @field_validator("texts", mode="before")
    @classmethod
    def _texts(cls, v: Any) -> list[str]:
        texts = [clean_text(str(t)) for t in (v if isinstance(v, list) else [v])]
        texts = [t for t in texts if t]
        if not texts:
            raise ValueError("a repair needs at least one text")
        return texts


class AdditionItem(LLMOut):
    after: str | None = None
    kind: str = "sentence"
    texts: list[str]
    fact_ids: list[str] = Field(default_factory=list)
    segment_ids: list[str] = Field(default_factory=list)

    _fids = field_validator("fact_ids", mode="before")(_fact_ids)
    _sids = field_validator("segment_ids", mode="before")(_segment_ids)
    _texts = field_validator("texts", mode="before")(RepairItem._texts.__func__)

    @field_validator("after", mode="before")
    @classmethod
    def _after(cls, v: Any) -> str | None:
        return normalize_id(v, "b", 3) if v else None

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, v: Any) -> str:
        return _BLOCK_KIND_ALIASES.get(str(v or "").strip().lower(), "sentence")


class RepairOut(LLMOut):
    _list_field = "repairs"

    repairs: list[RepairItem] = Field(default_factory=list)
    additions: list[AdditionItem] = Field(default_factory=list)
