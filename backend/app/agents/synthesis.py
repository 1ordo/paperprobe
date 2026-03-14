"""Synthesis Agent — validates consistency and computes worst scores.

Implements the COSMIN "worst score counts" principle:
- The overall rating per box equals the LOWEST rating of any individual standard in that box.
- Standards rated "na" are EXCLUDED from the worst-score computation.
- If ALL standards in a box are "na", the box is not applicable (returns None).
- Grey-cell standards that were auto-corrected should be flagged for human review.
"""
import logging

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

RATING_ORDER = {
    "very_good": 4,
    "adequate": 3,
    "doubtful": 2,
    "inadequate": 1,
    "na": None,
}

RATING_REVERSE = {4: "very_good", 3: "adequate", 2: "doubtful", 1: "inadequate"}


def compute_worst_score(ratings: list[str]) -> str | None:
    """Apply the COSMIN 'worst score counts' principle.

    Per the COSMIN user manual: the lowest rating of any standard within a box
    determines the overall methodological quality rating for that box.
    Standards rated 'na' (not applicable) are excluded.

    Returns None if all ratings are 'na' or list is empty.
    """
    scores = [RATING_ORDER[r] for r in ratings if r in RATING_ORDER and RATING_ORDER[r] is not None]
    if not scores:
        return None
    return RATING_REVERSE[min(scores)]


SYSTEM_PROMPT = """\
You are a COSMIN methodology expert reviewing AI-generated Risk of Bias ratings for \
consistency and accuracy. You understand the COSMIN V3.0 checklist and the "worst score \
counts" principle thoroughly.

Your task is to:
1. Review the ratings assigned to each standard within each COSMIN box.
2. Check for LOGICAL INCONSISTENCIES — for example:
   - A design requirement rated "very_good" when the evidence shows the requirement wasn't met.
   - A statistical method rated "very_good" when the method doesn't match the study design.
   - Conflicting ratings for related standards (e.g., sample size rated very_good in one \
     standard but the same sample is considered inadequate for another analysis).
   - The "other flaws" standard should not have "adequate" (it's a grey cell).
3. Verify the "worst score counts" principle: the box-level rating equals the LOWEST \
   individual standard rating (excluding NA).
4. Flag any ratings that seem questionable or need human review, especially:
   - Ratings with low confidence scores
   - Auto-corrected ratings (grey cell violations)
   - Standards where evidence was sparse
5. Provide an overall quality summary considering all evaluated boxes.

Important: The worst score counts principle means that even ONE inadequate standard \
makes the entire box "inadequate". This is by design — it reflects the most conservative \
assessment of risk of bias.

Respond with a JSON object.
"""

USER_PROMPT_TEMPLATE = """\
Review the following COSMIN Risk of Bias ratings for consistency.

{ratings_summary}

## Computed worst scores (mechanical application of worst-score-counts):
{worst_scores_summary}

Respond with this JSON format:
{{
    "box_summaries": [
        {{
            "box_number": number,
            "worst_score": "mechanically computed worst score",
            "override_suggestion": null or "suggested different score with reasoning",
            "consistency_issues": ["list of any inconsistency concerns"],
            "flags_for_review": ["list of items that need human reviewer attention"],
            "confidence": 0.0-1.0,
            "summary": "brief plain-language summary of this box's assessment"
        }}
    ],
    "overall_quality": "brief overall assessment of the paper's methodological quality",
    "key_concerns": ["top concerns across all boxes"],
    "recommendations_for_reviewers": ["specific things human reviewers should double-check"]
}}
"""


class SynthesisAgent(BaseAgent):
    """Validates rating consistency and computes box-level worst scores."""

    def __init__(self, paper_id: str, **kwargs):
        super().__init__(paper_id, model=settings.ai_model_primary, **kwargs)

    async def synthesize(self, all_ratings: dict[int, list[dict]]) -> dict:
        """Synthesize all box ratings into a consistent assessment.

        Args:
            all_ratings: Dict mapping box_number -> list of standard rating dicts.

        Returns:
            Synthesis result with worst scores and consistency check.
        """
        # First compute worst scores mechanically
        box_worst_scores = {}
        for box_num, ratings in all_ratings.items():
            rating_values = [r["rating"] for r in ratings if r.get("rating")]
            worst = compute_worst_score(rating_values)
            box_worst_scores[box_num] = worst

        # Format ratings summary for the LLM
        summary_parts = []
        for box_num, ratings in sorted(all_ratings.items()):
            worst = box_worst_scores.get(box_num, "N/A")
            summary_parts.append(f"\n## Box {box_num} (Computed Worst Score: {worst})")
            for r in ratings:
                auto_corrected = "[AUTO-CORRECTED] " if "Auto-corrected" in r.get("reasoning", "") else ""
                summary_parts.append(
                    f"  Standard {r.get('standard_number', '?')}: {auto_corrected}{r.get('rating', '?')} "
                    f"(confidence: {r.get('confidence', '?')}) — {r.get('reasoning', 'no reasoning')[:300]}"
                )

        ratings_summary = "\n".join(summary_parts)

        # Format worst scores summary
        worst_parts = []
        for box_num, worst in sorted(box_worst_scores.items()):
            rating_values = [r["rating"] for r in all_ratings.get(box_num, []) if r.get("rating")]
            na_count = rating_values.count("na")
            total = len(rating_values)
            worst_parts.append(
                f"Box {box_num}: {worst or 'N/A (all standards are NA)'} "
                f"({total} standards rated, {na_count} NA excluded)"
            )
        worst_scores_summary = "\n".join(worst_parts)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            ratings_summary=ratings_summary,
            worst_scores_summary=worst_scores_summary,
        )

        result = await self.call_llm(SYSTEM_PROMPT, user_prompt, json_mode=True, temperature=0.0)

        # Merge computed worst scores with LLM analysis
        result["computed_worst_scores"] = box_worst_scores

        logger.info(f"Paper {self.paper_id}: synthesis complete for {len(all_ratings)} boxes")
        return result
