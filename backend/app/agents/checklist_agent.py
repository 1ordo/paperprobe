"""Checklist Agent — rates individual COSMIN standards for a specific box.

Implements the COSMIN Risk of Bias V3.0 (August 2024) rating methodology
as described in the official user manual. Two categories of standards exist:

1. Design requirements — rated on evidence provided vs. assumable vs. unclear
2. Preferred statistical methods — rated on whether preferred method matches study design

The agent must respect "grey cells" (empty rating criteria) — those rating levels
do not exist for that standard and must never be assigned.

Temperature is set to 0.0 for maximum consistency across runs.
"""
import logging

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — provides the COSMIN rating methodology so the AI applies
# consistent, manual-aligned criteria to each standard.
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an experienced COSMIN Risk of Bias reviewer applying the COSMIN Risk of Bias \
checklist V3.0 (27 August 2024). You combine strict adherence to the COSMIN methodology \
with the domain knowledge expected of a senior systematic reviewer.

## RATING METHODOLOGY (from the COSMIN user manual)

Each standard falls into one of two categories. Apply the correct logic:

### Design Requirements
- **very_good**: Evidence or convincing arguments explicitly provided that the standard was met.
- **adequate**: Assumable that the standard was met, although not explicitly described. \
This includes common practice, information implied by other details, use of well-established \
instruments/methods, and standard procedures that can be reasonably inferred.
- **doubtful**: Unclear whether the standard was met.
- **inadequate**: Evidence that the standard was NOT met.

### Preferred Statistical Methods
- **very_good**: A preferred method was optimally used — the specific model/formula is \
described and matches the study design and comprehensive research question.
- **adequate**: A preferred method was used, but not optimally — e.g., formula doesn't \
perfectly match design, or insufficient detail to verify, but no evidence of error.
- **doubtful**: Unclear whether a preferred method was used or matches the design.
- **inadequate**: Statistical methods used are considered inadequate.

## THE "OTHER IMPORTANT FLAWS" STANDARD

Every box ends with this catch-all standard. Its rating criteria from the COSMIN checklist:
- **very_good** = "No other important methodological flaws" — THIS IS THE DEFAULT.
- **adequate** = GREY CELL (does not exist — never assign).
- **doubtful** = "Other minor methodological flaws"
- **inadequate** = "Other important methodological flaws"

Rules for this standard:
1. DEFAULT to "very_good" unless you identify a SPECIFIC flaw not already captured by \
the other standards in the same box.
2. Do NOT double-count: if a concern is already addressed by another standard in the \
box (sample size, ICC model, time interval, etc.), it cannot also be cited here.
3. Instrument characteristics (ceiling effects, brevity, limited item coverage) are NOT \
"flaws in the design or statistical methods of the study."
4. Contextual limitations noted in the discussion section are NOT methodological flaws \
unless they represent a concrete bias in the study design.
5. Only rate "doubtful" or "inadequate" if you can name a specific flaw and explain \
why it is not already captured by another standard.

## GREY CELLS — ABSOLUTE RULE
The standards provided below include their available rating options. If a rating level \
shows "GREY - not available", that option does NOT exist for that standard. You MUST \
NEVER assign a grey-cell rating.

## NA (Not Applicable)
Only assign "na" when the standard explicitly allows it AND the measurement property \
truly does not apply to this study's design.

## EVIDENCE QUOTES — ABSOLUTE RULES
1. Evidence quotes MUST be VERBATIM text copied exactly from the paper excerpts provided.
2. NEVER paraphrase, summarize, or generate text. Copy the exact words.
3. If no verbatim quote supports the rating, write "No direct quote available."
4. Page numbers MUST come from the [Page X] markers in the paper excerpts.
5. NEVER guess or fabricate page numbers. Only use page numbers you can see in the text.

## JUDGMENT PRINCIPLES
- "Not explicitly stated" ≠ "inadequate". Use the "assumable" concept appropriately.
- Reserve "inadequate" for clear violations with evidence, not mere omissions.
- Apply consistent judgment across all standards — do not be harsher on some without reason.
- Ask yourself: "Would another experienced COSMIN reviewer agree with this rating?"

Respond with a JSON object.
"""

USER_PROMPT_TEMPLATE = """\
Rate the following COSMIN standards for Box {box_number}: {box_name}.

{sub_box_info}

## Standards to rate:
{standards_text}

## Extracted evidence from the paper:
{evidence}

## Relevant paper excerpts:
{context}

## Instructions:
For EACH standard, follow this process:

1. **Identify the category**: Is it a "Design requirement" or "Preferred statistical method"? \
(Check the section_group field.)
2. **Search the paper thoroughly**: Read ALL the paper excerpts — intro, methods, results, \
discussion, and tables. Evidence may appear anywhere.
3. **Apply domain knowledge**: If the paper uses well-known instruments, methods, or procedures, \
apply what you know. "Assumable" means you can use your expertise.
4. **Check grey cells**: If a rating level shows "GREY - not available", it is NOT a valid option.
5. **For "other flaws" standards**: Default to "very_good" unless you can identify a specific \
flaw NOT already covered by the other standards in this box. Do NOT double-count.
6. **Rate fairly**: Ask — "Would another experienced COSMIN reviewer agree?"
7. **Evidence quotes**: Copy VERBATIM text from the paper excerpts above. Include page numbers \
from [Page X] markers. NEVER fabricate quotes or page numbers.

Respond with this JSON format:
{{
    "ratings": [
        {{
            "standard_id": database_id_integer,
            "standard_number": standard_number,
            "rating": "very_good|adequate|doubtful|inadequate|na",
            "confidence": 0.0-1.0,
            "reasoning": "detailed explanation citing the COSMIN rating logic applied",
            "evidence_quotes": [
                {{"text": "VERBATIM quote from paper excerpts (never fabricated)", "page": page_number_from_bracket_markers}}
            ]
        }}
    ]
}}
"""


def format_standards_for_prompt(standards: list[dict]) -> str:
    """Format standards into a readable prompt section.

    Grey cells (empty rating criteria) are clearly marked so the LLM knows
    which rating levels are not available for each standard.
    """
    parts = []
    for std in standards:
        vg = std.get("rating_very_good") or ""
        ad = std.get("rating_adequate") or ""
        db = std.get("rating_doubtful") or ""
        iq = std.get("rating_inadequate") or ""

        def fmt_rating(label: str, text: str) -> str:
            if not text.strip():
                return f"  - {label}: GREY - not available (do NOT assign this rating)"
            return f"  - {label}: {text}"

        section = std.get("section_group", "")
        section_line = f"\n  Section: {section}" if section else ""

        part = f"""Standard {std['standard_number']}: {std['question_text']}{section_line}
{fmt_rating('Very Good', vg)}
{fmt_rating('Adequate', ad)}
{fmt_rating('Doubtful', db)}
{fmt_rating('Inadequate', iq)}
  - N/A allowed: {'Yes' if std.get('na_allowed') else 'No'}
  - Database ID: {std['id']}"""
        parts.append(part)
    return "\n\n".join(parts)


def _format_evidence_readable(evidence: dict) -> str:
    """Format the extracted evidence dict into clean human-readable text.

    Avoids dumping raw Python dicts/lists into the prompt, which confuses
    the LLM and leads to it quoting structured data instead of paper text.
    """
    parts = []

    # Sample size
    ss = evidence.get("sample_size")
    if ss:
        if isinstance(ss, dict):
            total = ss.get("total", "not reported")
            items = ss.get("items_count")
            ratio = ss.get("ratio_per_item")
            line = f"Sample size: N={total}"
            if items:
                line += f", {items} items"
            if ratio:
                line += f" (ratio {ratio} per item)"
            how = ss.get("how_determined")
            if how:
                line += f". Determined by: {how}"
            parts.append(line)
        else:
            parts.append(f"Sample size: {ss}")

    # Study design and population
    if evidence.get("study_design"):
        parts.append(f"Study design: {evidence['study_design']}")
    if evidence.get("population"):
        parts.append(f"Population: {evidence['population']}")

    # Comprehensive research question
    crq = evidence.get("comprehensive_research_question")
    if crq and isinstance(crq, dict):
        crq_parts = []
        for key in ["construct", "target_population", "instrument_type", "instrument_name",
                     "operationalization", "measurement_conditions", "source_of_variation"]:
            val = crq.get(key)
            if val:
                crq_parts.append(f"  - {key.replace('_', ' ').title()}: {val}")
        if crq_parts:
            parts.append("Research question elements:\n" + "\n".join(crq_parts))

    # Statistical methods
    methods = evidence.get("statistical_methods")
    if methods:
        if isinstance(methods, list):
            method_lines = []
            for m in methods:
                if isinstance(m, dict):
                    line = f"  - {m.get('method', 'Unknown method')}"
                    if m.get("details"):
                        line += f": {m['details']}"
                    if m.get("formula_or_model"):
                        line += f" [Model/Formula: {m['formula_or_model']}]"
                    if m.get("software"):
                        line += f" (software: {m['software']})"
                    if m.get("matches_study_design"):
                        line += f" — Design match: {m['matches_study_design']}"
                    method_lines.append(line)
                else:
                    method_lines.append(f"  - {m}")
            if method_lines:
                parts.append("Statistical methods:\n" + "\n".join(method_lines))
        else:
            parts.append(f"Statistical methods: {methods}")

    # Missing data
    md = evidence.get("missing_data")
    if md:
        if isinstance(md, dict):
            pct = md.get("percentage", "not reported")
            handling = md.get("handling_method", "not stated")
            parts.append(f"Missing data: {pct}% — handling: {handling}")
        else:
            parts.append(f"Missing data: {md}")

    # Time interval
    ti = evidence.get("time_interval")
    if ti:
        if isinstance(ti, dict):
            parts.append(f"Time interval: {ti.get('duration', 'not reported')}")
            if ti.get("stability_assumption"):
                parts.append(f"  Stability: {ti['stability_assumption']}")
        else:
            parts.append(f"Time interval: {ti}")

    # Comparator instruments
    comps = evidence.get("comparator_instruments")
    if comps and isinstance(comps, list):
        comp_lines = []
        for c in comps:
            if isinstance(c, dict):
                name = c.get("name", "Unknown")
                construct = c.get("construct", "")
                props = "properties reported" if c.get("properties_reported") else "properties NOT reported"
                exp_dir = c.get("expected_correlation_direction", "")
                exp_mag = c.get("expected_correlation_magnitude", "")
                line = f"  - {name} (measures: {construct}; {props})"
                if exp_dir:
                    line += f" [expected: {exp_dir}"
                    if exp_mag:
                        line += f", {exp_mag}"
                    line += "]"
                comp_lines.append(line)
            else:
                comp_lines.append(f"  - {c}")
        if comp_lines:
            parts.append("Comparator instruments:\n" + "\n".join(comp_lines))

    # Hypotheses
    hyp = evidence.get("hypotheses_formulated")
    if hyp:
        if isinstance(hyp, dict):
            a_priori = "yes" if hyp.get("a_priori") else "no/unclear"
            direction = "yes" if hyp.get("direction_specified") else "no"
            magnitude = "yes" if hyp.get("magnitude_specified") else "no"
            details = hyp.get("details", "")
            parts.append(f"Hypotheses: a priori={a_priori}, direction specified={direction}, magnitude specified={magnitude}")
            if details:
                parts.append(f"  Details: {details}")
        else:
            parts.append(f"Hypotheses: {hyp}")

    # Key results
    results = evidence.get("key_results")
    if results and isinstance(results, list):
        result_lines = []
        for r in results:
            if isinstance(r, dict):
                metric = r.get("metric", "")
                value = r.get("value", "")
                ci = r.get("ci_95")
                ctx = r.get("context", "")
                n = r.get("n")
                line = f"  - {metric} = {value}"
                if ci:
                    line += f" (95% CI: {ci})"
                if ctx:
                    line += f" [{ctx}]"
                if n:
                    line += f" n={n}"
                result_lines.append(line)
        if result_lines:
            parts.append("Key results:\n" + "\n".join(result_lines))

    # Potential flaws
    flaws = evidence.get("potential_flaws")
    if flaws and isinstance(flaws, list):
        flaw_lines = [f"  - {f}" for f in flaws if f]
        if flaw_lines:
            parts.append("Potential flaws noted:\n" + "\n".join(flaw_lines))

    return "\n\n".join(parts) if parts else "No structured evidence extracted."


class ChecklistAgent(BaseAgent):
    """Rates individual COSMIN standards for a specific box."""

    # Temperature 0.0 for maximum consistency across runs
    TEMPERATURE = 0.0

    def __init__(self, paper_id: str, **kwargs):
        super().__init__(paper_id, model=settings.ai_model_primary, **kwargs)

    async def rate_box(
        self,
        box_number: int,
        box_name: str,
        standards: list[dict],
        evidence: dict,
        document_text: str | None = None,
    ) -> list[dict]:
        """Rate all standards for a specific COSMIN box.

        Args:
            box_number: The COSMIN box number (1-10).
            box_name: The box name.
            standards: List of standard dicts with id, standard_number, question_text, rating criteria.
            evidence: Pre-extracted evidence from the EvidenceExtractor.
            document_text: Full document text (methods + results). If provided, used as
                primary context instead of vector search to ensure nothing is missed.

        Returns:
            List of rating dicts for each standard.
        """
        if document_text:
            # Use full document text — 128k context models can handle large papers.
            # Include as much as the model allows (leave room for prompt + response).
            context = document_text[:120000]
        else:
            # Fallback to vector search (RAG)
            box_queries = {
                1: ["PROM development", "concept elicitation qualitative interviews", "pilot testing cognitive debriefing"],
                2: ["content validity", "patient relevance comprehensiveness comprehensibility", "professional expert panel review"],
                3: ["factor analysis", "CFA confirmatory EFA exploratory Rasch IRT", "model fit RMSEA CFI TLI factor loadings"],
                4: ["internal consistency", "Cronbach alpha omega unidimensional reflective model"],
                5: ["cross-cultural translation", "forward backward translation measurement invariance DIF", "multi-group CFA"],
                6: ["test-retest reliability", "ICC intraclass correlation coefficient kappa", "time interval stable patients raters"],
                7: ["measurement error", "SEM standard error of measurement SDC smallest detectable change", "limits of agreement LoA coefficient of variation"],
                8: ["criterion validity", "gold standard sensitivity specificity AUC ROC"],
                9: ["construct validity hypothesis testing", "convergent discriminant correlation comparator instrument", "known groups comparison expected differences", "measures instruments tests what it measures construct assessed"],
                10: ["responsiveness change over time", "anchor-based criterion-based AUC ROC", "effect size change score hypothesis"],
            }

            queries = box_queries.get(box_number, [f"Box {box_number} {box_name}"])
            chunks = await self.retrieve_multi_context(queries, limit_per_query=6)
            context = self.format_context(chunks, max_chars=80000)

        standards_text = format_standards_for_prompt(standards)

        # Build sub-box info if standards span multiple sub-boxes
        sub_boxes_seen = set()
        for std in standards:
            sg = std.get("section_group", "")
            if sg:
                sub_boxes_seen.add(sg)
        sub_box_info = ""
        if sub_boxes_seen:
            sub_box_info = "This box contains standards in these sections: " + ", ".join(sorted(sub_boxes_seen))

        # Format evidence summary as human-readable text (NOT raw dicts)
        evidence_str = _format_evidence_readable(evidence)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            box_number=box_number,
            box_name=box_name,
            sub_box_info=sub_box_info,
            standards_text=standards_text,
            evidence=evidence_str,
            context=context,
        )

        result = await self.call_llm(
            SYSTEM_PROMPT,
            user_prompt,
            json_mode=True,
            temperature=self.TEMPERATURE,
        )
        ratings = result.get("ratings", [])

        # Build a lookup of valid ratings per standard (respecting grey cells)
        valid_per_standard = {}
        for std in standards:
            valid = {"na"} if std.get("na_allowed") else set()
            if (std.get("rating_very_good") or "").strip():
                valid.add("very_good")
            if (std.get("rating_adequate") or "").strip():
                valid.add("adequate")
            if (std.get("rating_doubtful") or "").strip():
                valid.add("doubtful")
            if (std.get("rating_inadequate") or "").strip():
                valid.add("inadequate")
            valid_per_standard[str(std["id"])] = valid

        # Validate and correct ratings
        all_valid = {"very_good", "adequate", "doubtful", "inadequate", "na"}
        for r in ratings:
            std_id = str(r.get("standard_id", ""))
            rating = r.get("rating")

            # Check if rating is a recognized value at all
            if rating not in all_valid:
                r["rating"] = "doubtful"
                r["reasoning"] = (r.get("reasoning", "") + " [Auto-corrected: invalid rating value]")
            # Check if rating is valid for this specific standard (grey cell check)
            elif std_id in valid_per_standard and rating not in valid_per_standard[std_id]:
                # The LLM assigned a grey-cell rating — downgrade to next available level
                available = valid_per_standard[std_id]
                if rating == "adequate" and "doubtful" in available:
                    r["rating"] = "doubtful"
                    r["reasoning"] = (r.get("reasoning", "") + " [Auto-corrected: 'adequate' is a grey cell for this standard, downgraded to 'doubtful']")
                elif rating == "adequate" and "very_good" in available:
                    r["rating"] = "very_good"
                    r["reasoning"] = (r.get("reasoning", "") + " [Auto-corrected: 'adequate' is a grey cell, upgraded to 'very_good']")
                elif "doubtful" in available:
                    r["rating"] = "doubtful"
                    r["reasoning"] = (r.get("reasoning", "") + f" [Auto-corrected: '{rating}' is a grey cell for this standard]")
                # else leave as-is if we can't find a valid alternative

            if not isinstance(r.get("confidence"), (int, float)):
                r["confidence"] = 0.5

        logger.info(f"Paper {self.paper_id}: rated Box {box_number} — {len(ratings)} standards")
        return ratings
