"""Evidence Extractor Agent — extracts key methodological details from paper.

Follows the COSMIN user manual data extraction recommendations (Step 5):
- Extract the 7 elements of a comprehensive research question
- Extract characteristics of included measurement instruments
- Extract information on feasibility and interpretability
- Extract statistical methods, models/formulas, and results
"""
import logging

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a research methodology expert specializing in psychometric studies and the \
COSMIN Risk of Bias methodology. Your task is to extract key methodological details \
from a research paper needed for COSMIN Risk of Bias assessment.

## WHAT TO EXTRACT (per COSMIN user manual)

### 1. Comprehensive Research Question Elements
For reliability and measurement error studies, extract the 7 elements:
1. Body function/structure or activity being measured (the construct)
2. Study population / target population
3. Type of measurement instrument (PROM, ClinROM, PerFOM, lab value)
4. Specific measurement instrument (name and version)
5. Operationalization — how the construct is measured (specific items, tasks, procedures)
6. Measurement conditions (setting, raters, time points)
7. Source of variation being evaluated (e.g., time/occasion, rater, method)

### 2. Study Characteristics
- Sample size(s) and how they were determined
- Study design (cross-sectional, longitudinal, test-retest, etc.)
- Population characteristics (diagnosis, age range, severity, setting)
- Missing data percentage and handling method

### 3. Statistical Methods
- Factor analysis type and details (CFA/EFA, rotation, estimation method)
- Reliability coefficients (ICC model, kappa type)
- Measurement error parameters (SEM, SDC, LoA formulas used)
- Software used
- Model/formula — specifically identify which formula was used (e.g., one-way random, \
two-way random, two-way mixed for ICC; agreement vs. consistency)

### 4. Comparator Instruments (for construct validity / hypotheses testing)
- Name and what it measures
- Whether its measurement properties are known/reported
- Direction and magnitude of expected correlations

### 5. Key Results
- All reported statistics with exact values and confidence intervals
- Effect sizes, correlation coefficients, ICC values, kappa values
- Factor loadings, fit indices (CFI, TLI, RMSEA, SRMR)
- Sample sizes per analysis

### 6. Evidence Quotes
- Direct quotes with page numbers for every key finding
- Prioritize methods section and results section quotes

Be precise with numbers and statistical details. Quote directly from the paper. \
If information is not found, explicitly state it is missing — do not fabricate data.

Respond with a JSON object.
"""

USER_PROMPT_TEMPLATE = """\
Extract key methodological evidence from the following paper excerpts for COSMIN \
Risk of Bias assessment.

The paper is being evaluated for these COSMIN boxes: {relevant_boxes}

Paper excerpts:
{context}

Respond with this JSON format:
{{
    "comprehensive_research_question": {{
        "construct": "what is being measured",
        "target_population": "who is the target population",
        "instrument_type": "PROM / ClinROM / PerFOM / lab value",
        "instrument_name": "specific instrument name and version",
        "operationalization": "how the construct is measured (items, tasks, etc.)",
        "measurement_conditions": "setting, raters, time points",
        "source_of_variation": "what is varied (time, rater, method, etc.)"
    }},
    "sample_size": {{
        "total": null or number,
        "per_group": null or dict of group: number,
        "items_count": null or number,
        "ratio_per_item": null or number,
        "how_determined": "power analysis / convenience / rule of thumb / not stated"
    }},
    "study_design": "detailed description of study design",
    "population": "target population description with inclusion/exclusion criteria",
    "statistical_methods": [
        {{
            "method": "name (e.g., CFA, ICC two-way random agreement, weighted kappa)",
            "details": "specifics (e.g., WLSMV estimation, absolute agreement, single measures)",
            "formula_or_model": "specific formula/model used if identifiable",
            "software": "if mentioned",
            "matches_study_design": "assessment of whether method matches the study design"
        }}
    ],
    "missing_data": {{
        "percentage": null or number,
        "handling_method": "listwise deletion / imputation / FIML / not stated"
    }},
    "time_interval": {{
        "duration": "for test-retest, e.g. '2 weeks'",
        "stability_assumption": "any evidence patients were stable between measurements"
    }},
    "comparator_instruments": [
        {{
            "name": "instrument name",
            "construct": "what it measures",
            "properties_reported": true/false,
            "expected_correlation_direction": "positive/negative/none stated",
            "expected_correlation_magnitude": "strong/moderate/weak/not stated"
        }}
    ],
    "hypotheses_formulated": {{
        "a_priori": true/false,
        "direction_specified": true/false,
        "magnitude_specified": true/false,
        "details": "description of specific hypotheses"
    }},
    "key_results": [
        {{
            "metric": "e.g. ICC(2,1) agreement",
            "value": "0.89",
            "ci_95": "[0.82, 0.94] or null",
            "context": "total scale / subscale name / subgroup",
            "n": "sample size for this specific analysis"
        }}
    ],
    "evidence_quotes": [
        {{
            "text": "direct quote from the paper",
            "page": page_number_or_null,
            "relevance": "what COSMIN standard this is evidence for"
        }}
    ],
    "potential_flaws": [
        "list of any methodological concerns noticed during extraction"
    ]
}}
"""


class EvidenceExtractor(BaseAgent):
    """Extracts structured evidence from a paper for COSMIN evaluation."""

    def __init__(self, paper_id: str, **kwargs):
        super().__init__(paper_id, model=settings.ai_model_primary, **kwargs)

    async def extract(self, relevant_boxes: list[int], document_text: str | None = None) -> dict:
        """Extract methodological evidence relevant to the specified COSMIN boxes.

        Args:
            relevant_boxes: List of COSMIN box numbers (1-10) that apply.
            document_text: Full paper text. If provided, used directly instead of vector search.

        Returns:
            Structured evidence dict.
        """
        if document_text:
            # Use full document text — 128k context can handle it
            context = document_text[:80000]
        else:
            # Fallback to vector search
            queries = [
                "study design methods sample size population inclusion exclusion criteria",
                "measurement instrument description construct measured",
            ]

            box_queries = {
                1: "PROM development concept elicitation qualitative pilot testing cognitive debriefing",
                2: "content validity patients professionals relevance comprehensiveness comprehensibility",
                3: "factor analysis CFA EFA IRT Rasch model fit indices CFI RMSEA TLI factor loadings",
                4: "internal consistency Cronbach alpha omega unidimensional reflective model",
                5: "cross-cultural translation forward backward measurement invariance DIF multi-group CFA",
                6: "test-retest reliability ICC intraclass correlation kappa inter-rater intra-rater time interval",
                7: "measurement error SEM SDC smallest detectable change limits of agreement LoA coefficient of variation",
                8: "criterion validity gold standard AUC ROC sensitivity specificity",
                9: "construct validity convergent discriminant known-groups correlation hypothesis comparator instrument",
                10: "responsiveness change score effect size anchor-based criterion-based AUC before after treatment",
            }

            for box_num in relevant_boxes:
                if box_num in box_queries:
                    queries.append(box_queries[box_num])

            queries.append("results table statistics coefficients values confidence interval")

            chunks = await self.retrieve_multi_context(queries, limit_per_query=4)
            context = self.format_context(chunks, max_chars=40000)

        boxes_str = ", ".join(f"Box {b}" for b in relevant_boxes)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            relevant_boxes=boxes_str,
            context=context,
        )

        result = await self.call_llm(SYSTEM_PROMPT, user_prompt, json_mode=True, temperature=0.0)
        logger.info(f"Paper {self.paper_id}: extracted evidence for boxes {relevant_boxes}")
        return result
