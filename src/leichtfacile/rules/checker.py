"""Run the registered rules over a draft and compute the document metrics.

No model is involved: the checker takes milliseconds per block, so it runs after every
write and every repair round.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable

from leichtfacile.rules import de as de_rules
from leichtfacile.rules import fr as fr_rules
from leichtfacile.rules import it as it_rules
from leichtfacile.rules.base import (
    RULES,
    BlockInfo,
    Context,
    Hit,
    glossary_keys,
    params_for,
    rules_for,
)
from leichtfacile.rules.document import DocInput, fact_coverage
from leichtfacile.rules.nlp import has_analysis, pipeline
from leichtfacile.schemas import (
    SEVERITY_RANK,
    Block,
    DocMetrics,
    Draft,
    FactSheet,
    Finding,
    Level,
    RuleFindings,
    SourceDocument,
    base_lang,
)

_SEGMENT_KINDS = {"heading": "heading", "list_item": "list_item"}


def source_as_draft(doc: SourceDocument, level: Level = "A2") -> Draft:
    """A text as it stands, as a draft to check: one block per segment, with its
    provenance. The `check` command, the Check page, the checker calibration and the
    SOURCE and REF rows of the evaluation measure texts this way."""
    blocks = [
        Block(
            id=f"b{i:04d}",
            kind=_SEGMENT_KINDS.get(seg.kind, "sentence"),  # type: ignore[arg-type]
            text=seg.text,
            segment_ids=[seg.id],
        )
        for i, seg in enumerate(doc.segments, 1)
    ]
    return Draft(
        doc_id=doc.id, lang=doc.lang, region=doc.region, level=level, blocks=blocks, origin="review"
    )


# The text talks to the reader: Sie or du (German), vous or tu (French), Lei or voi
# (Italian). The writer asks for the formal form, but a text in the informal one does
# address the reader, so LEX-06 must not add the reminder that it never does. The
# capitalised Italian forms count inside a sentence and at its start; voi in any case.
_ADDRESS_RE = {
    "de": re.compile(
        r"\b(?:Ihnen|Ihr|Ihre|Ihren|Ihrem|Ihrer|Ihres)\b|(?<=[a-zäöü,] )Sie\b"
        r"|(?i:\b(?:du|dich|dir|dein|deine|deinen|deinem|deiner|deines"
        r"|euch|euer|eure|euren|eurem|eurer|eures)\b)"
    ),
    "fr": re.compile(r"\b(?:vous|votre|vos|tu|toi|te|ton|ta|tes)\b|\bt['’](?=\w)", re.IGNORECASE),
    "it": re.compile(
        r"(?<=[a-zàèéìòù,] )(?:Lei|La|Le|Suo|Sua|Suoi|Sue)\b|(?:^|[.!?:]\s+)Lei\b"
        r"|(?i:\b(?:voi|vostr[oaie]|tu|ti|tuo|tua|tuoi|tue)\b)"
    ),
}
# Sentence analysis for the document metrics, per language with an analysis.
_ANALYSIS = {"de": de_rules, "fr": fr_rules, "it": it_rules}
_INTRODUCED_RE = re.compile(r"\(([A-ZÄÖÜ][A-Za-zÄÖÜäöü]{1,7})\)")  # (EL), (BehiG)


class RuleChecker:
    def __init__(self, lang: str) -> None:
        """`lang`: a language or a variety key (schemas.variety, `de-AT`): the checks and
        guides are the variety's where it has its own, the spaCy pipeline the language's."""
        self.variety = lang
        self.lang = base_lang(lang)
        self.nlp = pipeline(self.lang)
        # German and French: a full parse; Italian: the lexicon's lemma, part of speech
        # and morphology. The sentence rules run with either.
        self.parsed = has_analysis(self.nlp)
        # One spaCy pipeline per language, used by the worker threads and the web
        # requests (the Check page) at once: one text through it at a time, as
        # ingest/segment.py does with its sentencizer.
        self._lock = threading.Lock()

    # -- analysis -----------------------------------------------------------------

    def analyse(self, blocks: Iterable[Block]) -> list[BlockInfo]:
        blocks = list(blocks)
        with self._lock:
            docs = list(self.nlp.pipe([b.text for b in blocks]))
        return [
            BlockInfo(b.id, b.kind, b.text, list(doc.sents))
            for b, doc in zip(blocks, docs, strict=True)
        ]

    def context(self, draft: Draft, factsheet: FactSheet | None, infos: list[BlockInfo]) -> Context:
        terms = [g.term for g in draft.glossary]
        if factsheet:
            terms += [h.term for h in factsheet.hard_terms]
        text = draft.text()
        introduced = set(_INTRODUCED_RE.findall(text))
        introduced |= {t for t in terms if 2 <= len(t) <= 8 and not t.istitle() and t[:1].isupper()}
        return Context(
            lang=self.lang,
            params=params_for(self.lang, draft.level),
            variety=self.variety,
            glossary=glossary_keys(terms),
            blocks=infos,
            addresses_reader=bool(self.lang in _ADDRESS_RE and _ADDRESS_RE[self.lang].search(text)),
            introduced=introduced,
        )

    # -- checks -------------------------------------------------------------------

    def check(
        self,
        draft: Draft,
        *,
        source: SourceDocument | None = None,
        factsheet: FactSheet | None = None,
        mode: str = "standard",
    ) -> RuleFindings:
        infos = self.analyse(draft.blocks)
        ctx = self.context(draft, factsheet, infos)
        findings: list[Finding] = []

        sentence_rules = list(rules_for(self.variety, "sentence")) if self.parsed else []
        block_rules = list(rules_for(self.variety, "block"))
        for index, info in enumerate(infos):
            ctx.block_index = index
            for spec, check in block_rules:
                if info.kind in spec.kinds:
                    findings += self._findings(spec.id, check(info, ctx), ctx, info.id)
            for sent in info.sentences:
                for spec, check in sentence_rules:
                    if info.kind in spec.kinds:
                        findings += self._findings(spec.id, check(sent, ctx), ctx, info.id)

        doc = DocInput(
            draft=draft,
            source=source,
            factsheet=factsheet,
            sentences=[s.text for i in infos if i.kind != "heading" for s in i.sentences],
            mode=mode,
        )
        for scope in ("document", "factsheet"):
            for spec, check in rules_for(self.variety, scope):
                findings += self._findings(spec.id, check(doc, ctx), ctx, None)

        metrics = self.metrics(infos, draft, factsheet, source)
        return RuleFindings(
            draft_version=draft.version,
            level=draft.level,
            findings=_order(_dedupe(findings), [b.id for b in draft.blocks]),
            metrics=metrics,
        )

    def check_export(
        self, lines: list[str], level: Level, *, notice: str | None = None
    ) -> list[Finding]:
        """`notice`: the fixed text a decision's export begins and ends with (FACT-07)."""
        ctx = Context(
            lang=self.lang, params=params_for(self.lang, level), variety=self.variety, notice=notice
        )
        findings: list[Finding] = []
        for spec, check in rules_for(self.variety, "export"):
            findings += self._findings(spec.id, check(lines, ctx), ctx, None)
        return findings

    def _findings(
        self, rule_id: str, hits: Iterable[Hit], ctx: Context, block_id: str | None
    ) -> list[Finding]:
        spec = RULES[rule_id]
        return [
            Finding(
                block_id=hit.block_id or block_id,
                rule_id=rule_id,
                severity=hit.severity or spec.severity_for(ctx.level),
                key=hit.key,
                params=dict(hit.params),
                evidence=hit.evidence,
                suggestion=hit.suggestion,
                fact_id=hit.fact_id,
                segment_ids=list(hit.segment_ids),
            )
            for hit in hits
        ]

    # -- metrics ------------------------------------------------------------------

    def metrics(
        self,
        infos: list[BlockInfo],
        draft: Draft,
        factsheet: FactSheet | None,
        source: SourceDocument | None = None,
    ) -> DocMetrics:
        from leichtfacile.rules.readability import readability

        sentences = [s for i in infos if i.kind != "heading" for s in i.sentences]
        analysis = _ANALYSIS.get(self.lang) if self.parsed else None
        if analysis is not None:
            counts = [analysis.word_count(s) for s in sentences]
            passive = sum(1 for s in sentences if analysis.passive_constructions(s))
            genitive = sum(1 for s in sentences if analysis.genitives(s))
            subordinate = sum(1 for s in sentences if analysis.subordinators(s))
        else:
            counts = [len([t for t in s if not (t.is_punct or t.is_space)]) for s in sentences]
            passive = genitive = subordinate = 0
        n = len(sentences)
        result = readability([s.text for s in sentences], self.variety)
        metrics = DocMetrics(
            blocks=len(infos),
            sentences=n,
            words=sum(counts),
            avg_words=round(sum(counts) / n, 2) if n else 0.0,
            max_words=max(counts, default=0),
            pct_passive=round(100 * passive / n, 1) if n else 0.0,
            pct_genitive=round(100 * genitive / n, 1) if n else 0.0,
            pct_subordinate=round(100 * subordinate / n, 1) if n else 0.0,
            readability=round(result.score, 1) if result.score is not None else None,
            readability_formula=result.formula,
        )
        if factsheet:
            coverage = fact_coverage(draft, factsheet, self.variety, source)
            metrics.facts_total = len(coverage.checkable)
            metrics.facts_found = len(coverage.found)
            ratio = coverage.ratio
            metrics.fact_coverage = round(ratio, 3) if ratio is not None else None
        return metrics


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple] = set()
    out = []
    for f in findings:
        key = (f.block_id, f.rule_id, f.key, tuple(sorted(f.params.items())), f.evidence)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def _order(findings: list[Finding], block_order: list[str]) -> list[Finding]:
    position = {bid: i for i, bid in enumerate(block_order)}
    return sorted(
        findings,
        key=lambda f: (
            position.get(f.block_id, len(position)) if f.block_id else len(position) + 1,
            SEVERITY_RANK[f.severity],
        ),
    )


_CHECKERS: dict[str, RuleChecker] = {}
_CHECKERS_LOCK = threading.Lock()


def get_checker(lang: str) -> RuleChecker:
    """The checker of a language or variety key; the varieties of one language share
    its spaCy pipeline (rules/nlp.py caches it)."""
    with _CHECKERS_LOCK:  # two threads must not load the same model twice
        if lang not in _CHECKERS:
            _CHECKERS[lang] = RuleChecker(lang)
        return _CHECKERS[lang]


def check_draft(
    draft: Draft,
    *,
    source: SourceDocument | None = None,
    factsheet: FactSheet | None = None,
    mode: str = "standard",
) -> RuleFindings:
    """`mode`: the job mode (schemas.JobMode); FACT-08 runs for a decision only."""
    return get_checker(draft.variety).check(draft, source=source, factsheet=factsheet, mode=mode)
