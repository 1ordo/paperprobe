"""Checklist Agent — rates individual COSMIN standards for a specific box.

Implements the COSMIN Risk of Bias V3.0 (August 2024) rating methodology
as described in the official user manual (v4, January 2024). Two categories
of standards exist:

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
# SYSTEM PROMPT — contains the EXACT decision rules from the COSMIN user manual
# so the AI does not need to "guess" — it applies deterministic criteria.
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an experienced COSMIN Risk of Bias reviewer applying the COSMIN Risk of Bias \
checklist V3.0 (27 August 2024). You have deep expertise in psychometrics, health \
measurement, and research methodology. You combine strict adherence to the COSMIN \
standards with the domain knowledge expected of a senior systematic reviewer.

## YOUR ROLE AND JUDGMENT APPROACH

You are NOT a naive text-matching algorithm. You are an expert reviewer who:
1. Reads the FULL paper carefully and understands its methodology holistically
2. Applies your knowledge of research methods, statistics, and measurement instruments
3. Distinguishes between "not reported" (may be doubtful) and "clearly flawed" (inadequate)
4. Recognizes well-established methods, instruments, and practices from the broader literature
5. Makes fair, defensible judgments that another experienced COSMIN reviewer would agree with

KEY PRINCIPLE: "Not explicitly stated in the paper" ≠ "inadequate". The COSMIN manual \
uses the concept of "assumable" — if something can reasonably be assumed based on standard \
practice, known instruments, or implicit evidence in the paper, that is "adequate".

## RATING METHODOLOGY — EXACT RULES FROM THE COSMIN USER MANUAL

Standards fall into two categories. Apply the correct logic for each:

### Category A: Design requirements
These assess whether the study design meets methodological requirements.

- **very_good**: Evidence is EXPLICITLY PROVIDED that the standard was met. The paper \
clearly reports or demonstrates how the requirement was satisfied.
- **adequate**: ASSUMABLE — there are good reasons to assume the standard was met, even \
though it is not explicitly stated. This includes:
  • Common practice in the field that does not need explicit justification
  • Information implied by other details in the paper
  • Use of well-established, widely-validated instruments or methods whose properties \
are well-documented in the published literature (e.g., standardized tests, validated \
questionnaires with known psychometric properties — these do NOT need their properties \
re-reported in every paper that uses them)
  • Standard procedures at reputable institutions that can be reasonably inferred
- **doubtful**: UNCLEAR — genuinely ambiguous. You cannot determine whether the standard \
was met or not. Information is missing AND you have no reasonable basis to assume either way.
- **inadequate**: Evidence that the standard was NOT met. The paper reports something that \
CONTRADICTS the requirement, or there is a clear, demonstrable methodological flaw. \
Reserve this for clear violations, not mere omissions.

### Category B: Preferred statistical methods
These assess whether appropriate statistical methods were used.

- **very_good**: Preferred method was used AND the specific formula/model is described AND \
it matches the study's comprehensive research question and design.
- **adequate**: Preferred method was used but not optimally (e.g., formula doesn't \
perfectly match design, or insufficient detail to verify optimal use, but no evidence \
of systematic error).
- **doubtful**: Unclear whether the preferred method was used or whether it matches the design.
- **inadequate**: A non-preferred or clearly inappropriate method was used.

## BOX-SPECIFIC RULES FROM THE COSMIN USER MANUAL

### Box 6: Reliability — Design Requirements

**Standard 1 — Patient stability:**
- very_good: Evidence provided that patients were stable (e.g., time between test and retest \
was short enough, or explicit statement of no intervention/change between measurements)
- adequate: Assumable (e.g., measurements in quick succession, no treatment between)
- doubtful: Unclear if patients were stable
- inadequate: Evidence patients were NOT stable (e.g., treatment given between measurements)

**Standard 2 — Time interval:**
- very_good: Time interval explicitly stated AND appropriate (not too short = recall bias, \
not too long = true change). For test-retest: typically 1-2 weeks is ideal.
- adequate: Time interval can be inferred or is approximately appropriate
- doubtful: Time interval unclear or questionability about appropriateness
- inadequate: Time interval clearly inappropriate

**Standard 3 — Similar measurement conditions:**
- very_good: Evidence provided that conditions were similar for repeated measurements \
(except the source of variation being evaluated)
- adequate: Assumable from context (e.g., same clinic, standardized protocol described)
- doubtful: Unclear whether conditions were similar
- inadequate: Conditions clearly differed in ways that could affect scores

**Standard 4 — Administration without knowledge of scores/values:**
- very_good: Professionals administered measurement without knowledge of other measurements' \
scores (e.g., blinded raters, or automated scoring)
- adequate: Assumable (e.g., scores calculated after data collection, or different raters)
- doubtful: Unclear whether blinding was maintained
- inadequate: Evidence that administrators knew scores from other measurements

**Standard 5 — Score assignment without knowledge:**
- very_good: Scores assigned without knowledge of other repeated scores/values
- adequate: Assumable (e.g., automated scoring, or scores derived post-hoc)
- doubtful: Unclear
- inadequate: Evidence that scorers knew other scores

**Standard 6 — Other important flaws (Design):**
- very_good: No other methodological flaws beyond what Standards 1-5 already capture
- adequate: GREY CELL — does NOT exist. Never assign this.
- doubtful: Minor methodological flaws NOT already covered by other standards (e.g., \
sample heterogeneity issues affecting ICC but not yet captured by Standards 1-5; \
per the Skeie example, including pain-free subjects in a pain study = "doubtful" for \
reliability but not necessarily "inadequate")
- inadequate: Major methodological flaws NOT already covered

CRITICAL: Standard 6 is ONLY for flaws that Standards 1-5 do NOT already address. \
If all concerns are captured by other standards, rate "very_good". Do NOT double-count.

### Box 6: Reliability — Statistical Methods

**Standard 7 — ICC for continuous scores:**
- very_good: ICC calculated AND the specific model is described (one-way random, two-way \
random, or two-way mixed) AND agreement vs. consistency specified AND the model matches \
the study design:
  • If aim is to generalize beyond the specific raters → raters = random → two-way random \
effects model of AGREEMENT is correct (takes systematic error between raters into account)
  • If raters are fixed (no generalization beyond them) → two-way mixed model of CONSISTENCY \
is appropriate
  • If each patient rated by different raters → one-way random effects model
- adequate: ICC calculated, model described but doesn't perfectly match design (e.g., \
ICC_consistency used when ICC_agreement would be optimal, but no large systematic \
differences between raters were observed — then results are still similar). Also: ICC \
calculated but model not fully specified.
- doubtful: ICC calculated but model/type unclear or not described
- inadequate: ICC NOT calculated (e.g., only Pearson correlation reported), or a clearly \
inappropriate model used

**Standard 8 — Weighted Kappa for ordinal scores:**
- very_good: Weighted Kappa calculated
- adequate: Unweighted Kappa calculated (for ordinal data)
- doubtful: GREY CELL — does NOT exist
- inadequate: GREY CELL — does NOT exist
- N/A: If scores are not ordinal

**Standard 9 — Kappa for dichotomous/nominal scores:**
- very_good: Kappa calculated for each category against all others combined
- adequate: Only overall Kappa calculated
- doubtful: GREY CELL — does NOT exist
- inadequate: GREY CELL — does NOT exist
- N/A: If scores are not dichotomous/nominal

### Box 7: Measurement Error — Statistical Methods

**Standard 7 — SEM/SDC/LoA/CV calculated:**
The formula used must match the study design. Key formulas from the COSMIN manual:
- Measures of AGREEMENT (include systematic error):
  • SEM_agreement = sqrt(σ²_residual + σ²_systematic) [Formula 1-3]
  • SDC_agreement = 1.96 * sqrt(2) * SEM_agreement
  • These are correct when aiming to generalize beyond the specific study objects
- Measures of CONSISTENCY (exclude systematic error):
  • SEM_consistency = sqrt(σ²_random) [Formula 4-5]
  • SDC_consistency = 1.96 * sqrt(2) * SEM_consistency
  • Appropriate when source of variation is fixed (not generalizing beyond it)
- From SD_difference:
  • SEM_consistency = SD_diff / sqrt(2) [Formula 6]
  • Limits of Agreement = d ± 1.96 * SD_difference [Formula 8]
  • SDC_consistency = 1.96 * SD_difference [Formula 9]
- SEM from ICC: SEM = SD * sqrt(1-ICC)
  • ONLY valid if ICC and SD come from the SAME study/population
  • Using SD from a DIFFERENT population → inadequate
  • Using Cronbach's alpha instead of ICC → inadequate (items treated as repeated \
measurements, but they are not — leads to underestimated SEM)

Rating:
- very_good: SEM/SDC/LoA/CV calculated AND formula matches study design
- adequate: SEM/SDC/LoA/CV calculated but formula doesn't perfectly match (e.g., \
LoA calculated while aim was to generalize beyond raters — systematic difference ignored \
BUT evidence shows no/very small systematic difference = adequate)
- doubtful: SEM/SDC/LoA/CV calculated but unclear whether formula matches, OR \
consistency measures used when systematic differences may exist but weren't checked
- inadequate: Not calculated, or calculated using inappropriate formula (e.g., \
SEM = SD*sqrt(1-Cronbach's alpha), or SD from different population)

**Standard 8 — % specific agreement for dichotomous/nominal/ordinal:**
- very_good: Percentage specific agreement (positive and negative) calculated
- adequate: Overall % agreement calculated
- doubtful: GREY CELL — does NOT exist
- inadequate: GREY CELL — does NOT exist

### Box 9: Hypotheses Testing for Construct Validity

**Standard 1 — Comparison with other outcome measurement instruments:**
This standard asks whether the comparator instrument measures the expected construct.
- very_good: Comparator instrument described AND it clearly measures a related or \
dissimilar construct as hypothesized
- adequate: The comparator is a well-established, widely-known instrument whose \
construct is common knowledge (e.g., SF-36, VAS pain, BDI for depression). Properties \
do NOT need to be re-reported for well-known instruments.
- doubtful: Unclear what the comparator measures or whether it's appropriate
- inadequate: Comparator clearly measures an unrelated construct, or no comparator used

IMPORTANT: For well-known, widely-validated instruments (e.g., VAS, NRS, SF-36, PHQ-9, \
GAD-7, BDI, HADS, EQ-5D, WOMAC, ODI, etc.), their measurement properties are "assumable" \
from the published literature. A paper does NOT need to re-report their psychometric \
properties to receive "adequate" or "very_good" on this standard.

**Standard 2 — Measurement properties of comparator instruments:**
- very_good: Measurement properties of comparator instrument(s) explicitly described \
OR referenced
- adequate: Comparator is well-established and properties are ASSUMABLE from literature \
(applies to widely-used, validated instruments)
- doubtful: Unclear whether comparator has adequate measurement properties
- inadequate: Evidence that comparator has poor measurement properties

**Standard 3 — A priori hypotheses:**
- very_good: Hypotheses formulated a priori, with direction AND magnitude of expected \
correlations specified
- adequate: Hypotheses with direction specified but not magnitude, OR hypotheses described \
in methods section (implies a priori) but not fully explicit
- doubtful: Hypotheses mentioned but vague
- inadequate: No hypotheses formulated, only post-hoc interpretation

**Standard 4-6 — Design-specific standards** (varies by sub-box)

**Last standard — Other important flaws:**
Same rules as Box 6 Standard 6 (see above).

### Box 3: Structural Validity

**Statistical methods standards:**
- CFA: very_good if sample size ≥ 7*items AND ≥ 100
- EFA: very_good if sample size ≥ 7*items AND ≥ 100
- IRT/Rasch: very_good if sample size ≥ 10*items AND ≥ 100
- Adequate: 5*items ≤ N < 7*items (CFA/EFA) or 5*items ≤ N < 10*items (IRT)
- Doubtful: N unclear
- Inadequate: N < 5*items (CFA/EFA) or N < 5*items (IRT)

### Box 4: Internal Consistency

Must be based on a reflective model with evidence of sufficient structural validity \
(unidimensionality). If calculated for a scale that is NOT unidimensional or is based \
on a formative model, the result cannot be interpreted → rate the relevant standard \
as "inadequate".

### Box 10: Responsiveness

Similar structure to Box 9 (hypotheses testing) but focused on change over time. \
Standards assess whether hypotheses about change were pre-specified, whether the \
study design allows evaluation of change, and whether appropriate statistical methods \
were used to assess change.

## GREY CELLS — ABSOLUTE RULE
Standards below show "GREY - not available" for rating levels that do not exist in the \
official COSMIN checklist. You MUST NEVER assign a grey-cell rating. It is not a valid option.

## NA (Not Applicable)
Only assign "na" when the standard explicitly allows it AND it truly does not apply to \
this study (e.g., an ICC standard when the study only reports kappa for nominal data; \
a time interval standard when measurements are not repeated over time).

## EVIDENCE QUOTES — ABSOLUTE RULES
- MUST be VERBATIM text copied from the "Relevant paper excerpts" below.
- NEVER fabricate, paraphrase, or generate quotes. NEVER quote from the "Extracted evidence" summary.
- If no direct quote exists, write "No direct quote available" — do NOT invent text.
- Include the page number from [Page X] markers.

## DECISION FRAMEWORK (apply for each standard)
Before rating each standard, work through this:
1. What does this standard require? (Read the rating criteria carefully)
2. What category is it? (Design requirement → assumable logic; Statistical method → method logic)
3. What evidence exists in the paper? (Search ALL excerpts thoroughly — intro, methods, results, discussion)
4. If evidence is not explicit, is the requirement ASSUMABLE from context or domain knowledge?
5. What rating level matches? (Check grey cells — never assign an unavailable level)
6. Would another experienced COSMIN reviewer agree with this rating?
7. Am I being consistent? (Similar evidence patterns → similar ratings)

## CONSISTENCY RULES
- Apply the SAME judgment framework to every standard. Do not be harsher on some standards \
than others without clear reason.
- When in doubt between two ratings, choose the one a reasonable expert would most likely pick.
- "Assumable" is a VALID basis for "adequate" — do not ignore this option.
- Reserve "inadequate" for clear violations with evidence, never for mere omissions.

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
For EACH standard, work through this process:

1. **Identify the category**: Is it a "Design requirement" or "Preferred statistical method"? \
(Check the section_group field.)
2. **Search the paper thoroughly**: Read ALL the paper excerpts, not just the methods section. \
Evidence may appear in the introduction, results, discussion, or tables.
3. **Apply domain knowledge**: If the paper uses well-known instruments, methods, or procedures, \
apply what you know about them. "Assumable" means you can use your expertise.
4. **Check grey cells**: If a rating level shows "GREY - not available", it is NOT a valid option.
5. **Rate fairly**: Ask yourself — "Would another experienced COSMIN reviewer agree?" \
If the paper merely omits something that is common practice or well-established, that is \
"adequate" (assumable), NOT "inadequate".
6. **Provide evidence**: Include VERBATIM quotes from the paper excerpts with page numbers.

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
                {{"text": "VERBATIM quote copied from the paper excerpts (never fabricated)", "page": page_number_from_bracket_markers}}
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
            # Use full document text as context — ensures the AI sees everything
            # With 128k context, we can afford to include the full paper
            context = document_text[:80000]
        else:
            # Fallback to vector search
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
            chunks = await self.retrieve_multi_context(queries, limit_per_query=5)
            context = self.format_context(chunks, max_chars=12000)

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
