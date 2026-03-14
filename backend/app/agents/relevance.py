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

The 10 COSMIN boxes correspond to measurement properties:

1. **PROM development** — Did the study develop a NEW Patient-Reported Outcome Measure? \
Look for: concept elicitation (interviews, focus groups), item generation, pilot testing, \
cognitive debriefing. Only relevant for PROM development studies.

2. **Content validity** — Did the study evaluate the content validity of an existing PROM? \
Look for: patient/professional assessment of relevance, comprehensiveness, comprehensibility. \
Only relevant for studies that explicitly evaluate content validity.

3. **Structural validity** — Did the study evaluate structural validity? \
Look for: factor analysis (CFA, EFA), IRT analysis, Rasch analysis, dimensionality assessment.

4. **Internal consistency** — Did the study evaluate internal consistency? \
Look for: Cronbach's alpha, omega, KR-20. Note: internal consistency is only relevant \
for multi-item instruments based on a reflective model.

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
Look for: comparison to a gold standard, AUC, sensitivity, specificity. \
Only relevant when a recognized gold standard exists for the construct.

9. **Hypotheses testing for construct validity** — Did the study test hypotheses about \
relationships with other instruments or differences between known groups? \
Look for: correlations with other instruments, known-groups comparisons, convergent/discriminant validity. \
Sub-box 9a = comparison with other outcome measurement instruments. \
Sub-box 9b = comparison between subgroups.

10. **Responsiveness** — Did the study evaluate the instrument's ability to detect change over time? \
Look for: before/after treatment comparisons, change scores, anchor-based methods, \
AUC for responsiveness, correlations with change on anchor instruments.

A paper may address MULTIPLE measurement properties. Be thorough — if the paper reports \
ANY results for a measurement property, mark that box as relevant.

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
            # Use first ~6000 chars of abstract + methods + results
            context = document_text[:6000]
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
            chunks = await self.retrieve_multi_context(queries, limit_per_query=3)
            context = self.format_context(chunks, max_chars=6000)

        user_prompt = USER_PROMPT_TEMPLATE.format(context=context)
        result = await self.call_llm(SYSTEM_PROMPT, user_prompt, json_mode=True, temperature=0.0)

        # Validate
        if "relevant_boxes" not in result:
            result["relevant_boxes"] = []
        result["relevant_boxes"] = [b for b in result["relevant_boxes"] if 1 <= b <= 10]

        logger.info(f"Paper {self.paper_id}: relevant boxes = {result['relevant_boxes']}")
        return result
