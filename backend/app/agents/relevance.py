"""Relevance Classifier Agent — determines which COSMIN boxes apply to a paper.

Per the COSMIN methodology (Step 5 of the user manual): for each article, check
which measurement properties were evaluated and subsequently decide which COSMIN
boxes are relevant. A single paper may address multiple measurement properties.
"""
import logging

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a COSMIN Risk of Bias assessment specialist. Your task is to determine which \
COSMIN checklist boxes are relevant to a given research paper about an outcome \
measurement instrument (PROM, ClinROM, PerFOM, or laboratory value).

## CRITICAL DISTINCTION RULES

### Box 8 vs Box 9 — This is the most common source of error

**Box 8 (Criterion validity)** applies when:
- The study compares an instrument against a GOLD STANDARD or reference standard
- The study calculates sensitivity, specificity, AUC, ROC curves
- The study evaluates diagnostic accuracy (e.g., screening tool vs. full diagnostic assessment)
- Example: Comparing a brief screening test (MoCA) against a comprehensive neuropsychological battery
- Example: Comparing a questionnaire against a clinical diagnosis

**Box 9 (Hypotheses testing for construct validity)** applies when:
- The study tests PRE-SPECIFIED HYPOTHESES about relationships between the instrument \
and OTHER measurement instruments (convergent/discriminant validity)
- The study compares scores between KNOWN GROUPS expected to differ
- The study explicitly states hypotheses about expected direction and/or magnitude of correlations
- The comparisons are about CONSTRUCT VALIDITY, not diagnostic accuracy
- Example: "We hypothesized that our pain scale would correlate positively (r>0.5) with the VAS"
- Example: "We expected higher scores in patients with severe disease vs. mild disease"

KEY DIFFERENCE: If the study treats one instrument as the "truth" or "gold standard" and \
evaluates how well another instrument detects the same thing → Box 8 (Criterion validity). \
If the study compares instruments to understand WHAT the instrument measures (its construct) \
via hypothesized relationships → Box 9 (Hypotheses testing).

DO NOT mark Box 9 just because a study compares scores with other instruments. \
That alone is NOT hypotheses testing unless there are explicit a priori hypotheses about \
expected correlations or group differences for construct validation purposes.

## The 10 COSMIN boxes

1. **PROM development** — Did the study develop a NEW Patient-Reported Outcome Measure? \
Look for: concept elicitation (interviews, focus groups), item generation, pilot testing, \
cognitive debriefing. Only relevant for PROM development studies.

2. **Content validity** — Did the study evaluate the content validity of an existing PROM? \
Look for: patient/professional assessment of relevance, comprehensiveness, comprehensibility. \
Only relevant for studies that explicitly evaluate content validity.

3. **Structural validity** — Did the study evaluate structural validity? \
Look for: factor analysis (CFA, EFA), IRT analysis, Rasch analysis, dimensionality assessment. \
Only relevant for multi-item instruments based on a reflective model.

4. **Internal consistency** — Did the study evaluate internal consistency? \
Look for: Cronbach's alpha, omega, KR-20. Only relevant for multi-item instruments \
based on a reflective model. Must have evidence of unidimensionality/structural validity.

5. **Cross-cultural validity / Measurement invariance** — Did the study evaluate \
cross-cultural validity or measurement invariance? \
Look for: translation procedures, DIF analysis, multi-group CFA, measurement invariance testing.

6. **Reliability** — Did the study evaluate test-retest, inter-rater, or intra-rater reliability? \
Look for: ICC, kappa, repeated measurements, reliability coefficients. \
The source of variation is key: time (test-retest), raters (inter-rater), or occasions (intra-rater).

7. **Measurement error** — Did the study calculate measurement error parameters? \
Look for: SEM, SDC, LoA (Limits of Agreement), coefficient of variation. \
Note: measurement error is often reported alongside reliability (Box 6).

8. **Criterion validity** — Did the study evaluate criterion validity against a gold standard? \
Look for: comparison to a gold standard or reference standard, AUC, sensitivity, specificity, \
diagnostic accuracy, screening performance. Only relevant when a recognized gold standard \
or reference standard exists for the construct.

9. **Hypotheses testing for construct validity** — Did the study test EXPLICIT hypotheses \
about relationships with other instruments or differences between known groups? \
Sub-box 9a = comparison with other outcome measurement instruments (convergent validity). \
Sub-box 9b = comparison between subgroups (known-groups validity). \
REQUIRES explicit a priori hypotheses about expected direction/magnitude of correlations \
or group differences. Simply reporting correlations with other instruments is NOT enough.

10. **Responsiveness** — Did the study evaluate the instrument's ability to detect change over time? \
Look for: before/after treatment comparisons, change scores, anchor-based methods, \
AUC for responsiveness, correlations with change on anchor instruments.

## IMPORTANT RULES
- A paper may address MULTIPLE measurement properties — be thorough.
- But do NOT over-assign boxes. Only mark a box if the paper ACTUALLY evaluates that \
measurement property with results. Mentioning a concept is not enough.
- Pay special attention to Box 8 vs Box 9 distinction (see above).
- Read the FULL paper carefully before deciding.

Respond with a JSON object.
"""

USER_PROMPT_TEMPLATE = """\
Based on the following excerpts from a research paper, determine which COSMIN boxes (1-10) \
are relevant.

Paper excerpts:
{context}

Respond with a JSON object in this exact format:
{{
    "relevant_boxes": [list of box numbers, e.g. [3, 4, 6, 9]],
    "reasoning": {{
        "1": "brief explanation of why box 1 is/isn't relevant",
        "2": "...",
        "3": "...",
        "4": "...",
        "5": "...",
        "6": "...",
        "7": "...",
        "8": "...",
        "9": "...",
        "10": "..."
    }},
    "instrument_type": "PROM / ClinROM / PerFOM / laboratory value / unclear",
    "instrument_name": "name of the instrument being studied",
    "study_type": "brief description (e.g., 'validation study of PROM-X in chronic pain patients')"
}}
"""


class RelevanceClassifier(BaseAgent):
    """Determines which COSMIN boxes apply to a given paper."""

    def __init__(self, paper_id: str, **kwargs):
        super().__init__(paper_id, model=settings.ai_model_fast, **kwargs)

    async def classify(self, document_text: str | None = None) -> dict:
        """Classify which COSMIN boxes are relevant to this paper.

        Args:
            document_text: Optional pre-extracted text. If None, retrieves via vector search.

        Returns:
            Dict with relevant_boxes, reasoning, and study_type.
        """
        if document_text:
            # Use full document text — the fast model has sufficient context window.
            # Truncating caused missed context for Box 8 vs 9 distinction.
            context = document_text[:120000]
        else:
            # Retrieve relevant chunks via semantic search
            queries = [
                "study design measurement properties psychometric validation",
                "PROM development content validity qualitative",
                "factor analysis structural validity CFA IRT Rasch",
                "reliability test-retest ICC inter-rater kappa",
                "measurement error SEM SDC limits of agreement",
                "responsiveness change score effect size anchor",
                "criterion validity gold standard AUC sensitivity",
                "construct validity hypothesis convergent discriminant known-groups",
                "sample size participants methods statistical analysis results",
            ]
            chunks = await self.retrieve_multi_context(queries, limit_per_query=5)
            context = self.format_context(chunks, max_chars=40000)

        user_prompt = USER_PROMPT_TEMPLATE.format(context=context)
        result = await self.call_llm(SYSTEM_PROMPT, user_prompt, json_mode=True, temperature=0.0)

        # Validate
        if "relevant_boxes" not in result:
            result["relevant_boxes"] = []
        result["relevant_boxes"] = [b for b in result["relevant_boxes"] if 1 <= b <= 10]

        logger.info(f"Paper {self.paper_id}: relevant boxes = {result['relevant_boxes']}")
        return result
