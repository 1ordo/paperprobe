"""Analysis Pipeline — orchestrates all COSMIN agents for a complete assessment."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.relevance import RelevanceClassifier
from app.agents.extractor import EvidenceExtractor
from app.agents.checklist_agent import ChecklistAgent
from app.agents.synthesis import SynthesisAgent, compute_worst_score
from app.models.cosmin import CosminBox, CosminSubBox, CosminStandard
from app.models.assessment import PaperAssessment, StandardRating, RatingEvidence, BoxRating
from app.models.document import DocumentSection

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """Orchestrates the full COSMIN analysis pipeline for a paper."""

    def __init__(self, paper_id: str, session: Session):
        self.paper_id = paper_id
        self.session = session

    async def run(self, progress_callback: Callable | None = None) -> dict:
        """Run the complete COSMIN analysis pipeline.

        Steps:
            1. Relevance classification — which boxes apply?
            2. Evidence extraction — extract key methodological details
            3. Checklist rating — rate each standard per applicable box (parallel)
            4. Synthesis — validate consistency and compute worst scores

        Args:
            progress_callback: Optional callback(step_name, progress_float).
        """
        def report(step: str, pct: float):
            if progress_callback:
                progress_callback(step, pct)

        report("relevance", 0.05)

        # Get or create assessment
        assessment = self._get_or_create_assessment()

        # Step 1: Relevance Classification
        logger.info(f"Pipeline step 1: Relevance classification for paper {self.paper_id}")
        document_text = self._get_document_text()
        classifier = RelevanceClassifier(paper_id=self.paper_id)
        relevance_result = await classifier.classify(document_text=document_text)

        relevant_boxes = relevance_result.get("relevant_boxes", [])
        assessment.relevant_boxes = relevance_result
        assessment.status = "classifying"
        assessment.ai_started_at = datetime.now(timezone.utc)
        self.session.commit()

        if not relevant_boxes:
            logger.warning(f"No relevant boxes for paper {self.paper_id}")
            assessment.status = "completed"
            assessment.ai_completed_at = datetime.now(timezone.utc)
            self.session.commit()
            return {"relevant_boxes": [], "message": "No COSMIN boxes were deemed relevant."}

        report("extracting", 0.15)

        # Step 2: Evidence Extraction
        logger.info(f"Pipeline step 2: Evidence extraction for boxes {relevant_boxes}")
        extractor = EvidenceExtractor(paper_id=self.paper_id)
        evidence = await extractor.extract(relevant_boxes, document_text=document_text)

        report("rating", 0.25)

        # Step 3: Checklist Rating (parallel per box)
        logger.info(f"Pipeline step 3: Rating {len(relevant_boxes)} boxes")
        box_standards = self._load_box_standards(relevant_boxes)
        assessment.status = "rating"
        self.session.commit()

        all_ratings = {}
        tasks = []
        for box_num, (box_name, standards) in box_standards.items():
            agent = ChecklistAgent(paper_id=self.paper_id)
            task = agent.rate_box(
                box_number=box_num,
                box_name=box_name,
                standards=standards,
                evidence=evidence,
                document_text=document_text,
            )
            tasks.append((box_num, task))

        # Run box evaluations concurrently
        box_results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)

        for (box_num, _), result in zip(tasks, box_results):
            if isinstance(result, Exception):
                logger.error(f"Box {box_num} rating failed: {result}")
                all_ratings[box_num] = []
            else:
                all_ratings[box_num] = result

        # Store ratings in DB
        progress_per_box = 0.5 / max(len(all_ratings), 1)
        for i, (box_num, ratings) in enumerate(all_ratings.items()):
            standards = box_standards.get(box_num, (None, []))[1]
            self._store_ratings(assessment, ratings, standards)
            report("storing", 0.25 + (i + 1) * progress_per_box)

        self.session.commit()

        report("synthesizing", 0.80)

        # Step 4: Synthesis
        logger.info(f"Pipeline step 4: Synthesis")
        synthesis_agent = SynthesisAgent(paper_id=self.paper_id)
        synthesis = await synthesis_agent.synthesize(all_ratings)

        # Store box-level worst scores
        self._store_box_scores(assessment, all_ratings, synthesis)

        assessment.status = "completed"
        assessment.ai_completed_at = datetime.now(timezone.utc)
        self.session.commit()

        report("done", 1.0)

        return {
            "relevant_boxes": relevant_boxes,
            "ratings_count": sum(len(r) for r in all_ratings.values()),
            "synthesis": synthesis,
        }

    def _get_or_create_assessment(self) -> PaperAssessment:
        """Get existing or create new assessment for this paper.

        On re-analysis, deletes all old ratings, evidence, and box scores
        so the pipeline starts fresh.
        """
        assessment = (
            self.session.query(PaperAssessment)
            .filter(PaperAssessment.paper_id == self.paper_id)
            .first()
        )
        if assessment:
            # Clear old data — cascade handles RatingEvidence via StandardRating
            self.session.query(BoxRating).filter(
                BoxRating.assessment_id == assessment.id
            ).delete()
            self.session.query(RatingEvidence).filter(
                RatingEvidence.rating_id.in_(
                    self.session.query(StandardRating.id).filter(
                        StandardRating.assessment_id == assessment.id
                    )
                )
            ).delete(synchronize_session="fetch")
            self.session.query(StandardRating).filter(
                StandardRating.assessment_id == assessment.id
            ).delete()
            assessment.status = "pending"
            assessment.relevant_boxes = None
            assessment.ai_started_at = None
            assessment.ai_completed_at = None
            self.session.flush()
            logger.info(f"Cleared old assessment data for paper {self.paper_id}")
        else:
            assessment = PaperAssessment(paper_id=self.paper_id, status="pending")
            self.session.add(assessment)
            self.session.flush()
        return assessment

    def _get_document_text(self) -> str | None:
        """Get concatenated document text from sections with page markers.

        Each section is prefixed with a [Page X] marker so that downstream
        agents can attribute evidence quotes to the correct page number.
        """
        sections = (
            self.session.query(DocumentSection)
            .filter(DocumentSection.paper_id == self.paper_id)
            .order_by(DocumentSection.position_order)
            .all()
        )
        if not sections:
            return None

        parts = []
        for s in sections:
            page = s.page_start
            if page:
                parts.append(f"[Page {page}]\n{s.content}")
            else:
                parts.append(s.content)
        return "\n\n".join(parts)

    def _load_box_standards(self, box_numbers: list[int]) -> dict[int, tuple[str, list[dict]]]:
        """Load standards for the specified box numbers.

        Returns:
            Dict mapping box_number -> (box_name, list of standard dicts).
        """
        result = {}
        for box_num in box_numbers:
            box = (
                self.session.query(CosminBox)
                .filter(CosminBox.box_number == box_num)
                .first()
            )
            if not box:
                continue

            standards = (
                self.session.query(CosminStandard)
                .join(CosminSubBox, CosminStandard.sub_box_id == CosminSubBox.id)
                .filter(CosminSubBox.box_id == box.id)
                .order_by(CosminSubBox.sort_order, CosminStandard.sort_order)
                .all()
            )

            std_dicts = [
                {
                    "id": str(std.id),
                    "standard_number": std.standard_number,
                    "question_text": std.question_text,
                    "section_group": std.section_group,
                    "rating_very_good": std.rating_very_good,
                    "rating_adequate": std.rating_adequate,
                    "rating_doubtful": std.rating_doubtful,
                    "rating_inadequate": std.rating_inadequate,
                    "na_allowed": std.na_allowed,
                    "has_sub_criteria": std.has_sub_criteria,
                    "sort_order": std.sort_order,
                }
                for std in standards
            ]
            result[box_num] = (box.name, std_dicts)

        return result

    def _store_ratings(self, assessment: PaperAssessment, ratings: list[dict], standards: list[dict] | None = None):
        """Store standard ratings and evidence in the database.

        The LLM may return standard_id as the database integer ID or as the
        standard_number. We build a lookup to resolve both cases.
        """
        # Build lookups for resolving LLM output to actual DB integer IDs
        valid_ids: set[int] = set()
        number_to_id: dict[int, int] = {}
        if standards:
            for std in standards:
                sid = int(std["id"])
                valid_ids.add(sid)
                sn = std.get("standard_number")
                if sn is not None:
                    number_to_id[int(sn)] = sid

        for r in ratings:
            raw_id = r.get("standard_id")
            if raw_id is None:
                continue

            # Try to resolve to a valid integer standard ID
            std_id = None
            try:
                candidate = int(raw_id)
                if candidate in valid_ids:
                    # Direct match — LLM returned the actual DB id
                    std_id = candidate
                elif candidate in number_to_id:
                    # LLM returned standard_number instead of DB id
                    std_id = number_to_id[candidate]
                else:
                    # Unknown integer — try it as-is (may be from old schema)
                    std_id = candidate
            except (ValueError, TypeError):
                # Try string-based UUID matching as fallback
                try:
                    raw_str = str(raw_id)
                    # Check if any standard id matches this string
                    for sid in valid_ids:
                        if str(sid) == raw_str:
                            std_id = sid
                            break
                except Exception:
                    pass

            if std_id is None:
                logger.warning(f"Could not resolve standard_id from LLM: {raw_id}")
                continue

            # Upsert rating
            existing = (
                self.session.query(StandardRating)
                .filter(
                    StandardRating.assessment_id == assessment.id,
                    StandardRating.standard_id == std_id,
                )
                .first()
            )

            if existing:
                existing.ai_rating = r.get("rating")
                existing.ai_confidence = r.get("confidence")
                existing.ai_reasoning = r.get("reasoning")
                rating_obj = existing
                # Clear old evidence before adding fresh ones
                self.session.query(RatingEvidence).filter(
                    RatingEvidence.rating_id == existing.id
                ).delete()
            else:
                rating_obj = StandardRating(
                    assessment_id=assessment.id,
                    standard_id=std_id,
                    ai_rating=r.get("rating"),
                    ai_confidence=r.get("confidence"),
                    ai_reasoning=r.get("reasoning"),
                )
                self.session.add(rating_obj)
                self.session.flush()

            # Store evidence quotes
            for eq in r.get("evidence_quotes", []):
                evidence = RatingEvidence(
                    rating_id=rating_obj.id,
                    evidence_text=eq.get("text", ""),
                    page_number=eq.get("page"),
                    source="ai",
                )
                self.session.add(evidence)

    def _store_box_scores(self, assessment: PaperAssessment, all_ratings: dict, synthesis: dict):
        """Store box-level worst scores."""
        computed = synthesis.get("computed_worst_scores", {})
        for box_num, worst_score in computed.items():
            box_num_int = int(box_num) if isinstance(box_num, str) else box_num

            # Find the box ID
            box = (
                self.session.query(CosminBox)
                .filter(CosminBox.box_number == box_num_int)
                .first()
            )
            if not box:
                continue

            existing = (
                self.session.query(BoxRating)
                .filter(
                    BoxRating.assessment_id == assessment.id,
                    BoxRating.box_id == box.id,
                    BoxRating.sub_box_id == None,
                )
                .first()
            )

            if existing:
                existing.ai_worst_score = worst_score
            else:
                box_rating = BoxRating(
                    assessment_id=assessment.id,
                    box_id=box.id,
                    ai_worst_score=worst_score,
                )
                self.session.add(box_rating)
