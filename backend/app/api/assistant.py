"""
AI Assistant endpoint — agentic chat with tool calling.
Has access to the full paper text, COSMIN assessment results, and methodology knowledge.
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import (
    Paper, DocumentSection, DocumentChunk,
    PaperAssessment, StandardRating, RatingEvidence, BoxRating,
    CosminBox, CosminSubBox, CosminStandard,
)
from app.services.ai_client import AIClient

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Tool definitions (OpenAI function-calling format) ──────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_paper",
            "description": "Search the paper text for specific content. Use this to find passages about methods, results, sample sizes, instruments, statistics, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query — what to look for in the paper",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_box_ratings",
            "description": "Get the COSMIN ratings for a specific box number (1-10). Returns all standard ratings, evidence quotes, AI reasoning, and worst score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "box_number": {
                        "type": "integer",
                        "description": "COSMIN box number (1-10)",
                    }
                },
                "required": ["box_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ratings_overview",
            "description": "Get a summary of all COSMIN box ratings — which boxes are relevant and their worst scores.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper_section",
            "description": "Get a specific section of the paper by type (e.g. 'abstract', 'methods', 'results', 'discussion', 'references'). Returns full text of that section.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_type": {
                        "type": "string",
                        "description": "Section type to retrieve (abstract, methods, results, discussion, introduction, full_document, etc.)",
                    }
                },
                "required": ["section_type"],
            },
        },
    },
]

# ── System prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a COSMIN methodology expert and research assistant. You help researchers \
understand and interpret COSMIN Risk of Bias assessments of their papers.

## Your capabilities
- You have full access to the paper's text, sections, and parsed content
- You can look up specific COSMIN ratings, evidence, and AI reasoning for any box/standard
- You understand the COSMIN Risk of Bias checklist V3.0 thoroughly

## COSMIN background
The COSMIN Risk of Bias checklist evaluates measurement properties across 10 boxes:
1. PROM development  2. Content validity  3. Structural validity
4. Internal consistency  5. Cross-cultural validity/MI  6. Reliability
7. Measurement error  8. Criterion validity  9. Hypotheses testing
10. Responsiveness

Each standard is rated: Very Good / Adequate / Doubtful / Inadequate / N/A
The "worst score counts" principle: the lowest-rated standard determines the box rating.

Key concepts:
- "Assumable" = well-established instruments don't need properties re-reported (adequate, not inadequate)
- Grey cells = rating levels that don't exist for certain standards
- ICC model must match study design (one-way random, two-way random agreement, two-way mixed consistency)
- SEM = SD*sqrt(1-ICC) is only valid if ICC and SD come from the same study
- Sample size rules vary by box (e.g., 7*items for CFA, 100+ for IRT)

## Current paper context
{paper_context}

## Instructions
- Use the available tools to look up specific information before answering
- Always ground your answers in the actual paper text and assessment data
- When discussing ratings, cite the specific evidence from the paper
- Be precise about COSMIN methodology — don't guess rating rules
- If asked about something not in the paper, say so clearly
- Keep responses focused and concise
"""


# ── Request/Response models ────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    paper_id: str
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    message: str
    tool_calls_made: list[str]


# ── Tool execution ─────────────────────────────────────────────────────

async def execute_tool(
    tool_name: str,
    arguments: dict,
    paper_id: UUID,
    db: AsyncSession,
) -> str:
    """Execute a tool call and return the result as a string."""

    if tool_name == "search_paper":
        query = arguments.get("query", "").lower()
        sections = (await db.execute(
            select(DocumentSection)
            .where(DocumentSection.paper_id == paper_id)
            .order_by(DocumentSection.position_order)
        )).scalars().all()

        results = []
        for s in sections:
            content_lower = s.content.lower()
            if query in content_lower:
                # Find the matching region with context
                idx = content_lower.find(query)
                start = max(0, idx - 200)
                end = min(len(s.content), idx + len(query) + 200)
                snippet = s.content[start:end]
                page_info = f"(p.{s.page_start})" if s.page_start else ""
                results.append(f"[{s.section_type} {page_info}]: ...{snippet}...")

        if not results:
            # Fallback: search chunks for partial matches
            chunks = (await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.paper_id == paper_id)
                .order_by(DocumentChunk.chunk_index)
            )).scalars().all()
            query_words = query.split()
            for c in chunks:
                chunk_lower = c.chunk_text.lower()
                if any(w in chunk_lower for w in query_words if len(w) > 3):
                    page_info = f"(p.{c.page_number})" if c.page_number else ""
                    results.append(f"[chunk {c.chunk_index} {page_info}]: {c.chunk_text[:400]}...")
                    if len(results) >= 5:
                        break

        if results:
            return f"Found {len(results)} matches:\n\n" + "\n\n".join(results[:8])
        return "No matching text found in the paper."

    elif tool_name == "get_box_ratings":
        box_number = arguments.get("box_number")
        # Get the box
        box = (await db.execute(
            select(CosminBox)
            .options(
                selectinload(CosminBox.sub_boxes)
                .selectinload(CosminSubBox.standards)
            )
            .where(CosminBox.box_number == box_number)
        )).scalar_one_or_none()
        if not box:
            return f"Box {box_number} not found."

        # Get assessment
        assessment = (await db.execute(
            select(PaperAssessment)
            .options(
                selectinload(PaperAssessment.standard_ratings)
                .selectinload(StandardRating.evidence),
                selectinload(PaperAssessment.box_ratings),
            )
            .where(PaperAssessment.paper_id == paper_id)
        )).scalar_one_or_none()

        if not assessment:
            return "No assessment found for this paper."

        # Build rating map
        rating_map = {r.standard_id: r for r in assessment.standard_ratings}
        box_rating = next((br for br in assessment.box_ratings if br.box_id == box.id), None)

        lines = [f"## Box {box_number}: {box.name}"]
        if box_rating:
            lines.append(f"Worst score: {box_rating.ai_worst_score or 'N/A'}")
        lines.append("")

        for sub_box in box.sub_boxes:
            lines.append(f"### {sub_box.sub_box_code}: {sub_box.name}")
            for std in sub_box.standards:
                r = rating_map.get(std.id)
                if r:
                    lines.append(f"\nStandard {std.standard_number}: {std.question_text}")
                    lines.append(f"  AI Rating: {r.ai_rating} (confidence: {r.ai_confidence:.0%})" if r.ai_confidence else f"  AI Rating: {r.ai_rating}")
                    if r.ai_reasoning:
                        lines.append(f"  Reasoning: {r.ai_reasoning}")
                    if r.evidence:
                        for ev in r.evidence:
                            page = f" (p.{ev.page_number})" if ev.page_number else ""
                            lines.append(f"  Evidence{page}: \"{ev.evidence_text[:300]}\"")

        return "\n".join(lines)

    elif tool_name == "get_ratings_overview":
        assessment = (await db.execute(
            select(PaperAssessment)
            .options(selectinload(PaperAssessment.box_ratings))
            .where(PaperAssessment.paper_id == paper_id)
        )).scalar_one_or_none()

        if not assessment:
            return "No assessment found for this paper."

        boxes = (await db.execute(
            select(CosminBox).order_by(CosminBox.box_number)
        )).scalars().all()

        relevant = set(assessment.relevant_boxes.get("relevant_boxes", []) if assessment.relevant_boxes else [])
        br_map = {br.box_id: br for br in assessment.box_ratings}

        lines = [f"Assessment status: {assessment.status}", f"Relevant boxes: {sorted(relevant)}", ""]
        for box in boxes:
            br = br_map.get(box.id)
            is_rel = box.box_number in relevant
            score = br.ai_worst_score if br else "N/A"
            marker = "" if is_rel else " [not relevant]"
            lines.append(f"Box {box.box_number} ({box.name}): {score}{marker}")

        return "\n".join(lines)

    elif tool_name == "get_paper_section":
        section_type = arguments.get("section_type", "").lower()
        sections = (await db.execute(
            select(DocumentSection)
            .where(
                DocumentSection.paper_id == paper_id,
                DocumentSection.section_type.ilike(f"%{section_type}%"),
            )
            .order_by(DocumentSection.position_order)
        )).scalars().all()

        if not sections:
            # List available sections
            all_sections = (await db.execute(
                select(DocumentSection.section_type)
                .where(DocumentSection.paper_id == paper_id)
                .distinct()
            )).scalars().all()
            return f"Section '{section_type}' not found. Available: {', '.join(all_sections)}"

        parts = []
        for s in sections:
            header = s.heading or s.section_type
            page = f" (pp. {s.page_start}-{s.page_end})" if s.page_start else ""
            parts.append(f"### {header}{page}\n{s.content}")

        return "\n\n".join(parts)

    return f"Unknown tool: {tool_name}"


# ── Chat endpoint ──────────────────────────────────────────────────────

@router.post("/assistant/chat", response_model=ChatResponse)
async def assistant_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    paper_id = UUID(req.paper_id)

    # Load paper metadata
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Build paper context for system prompt
    paper_context = f"Title: {paper.title or paper.filename}\n"
    if paper.authors:
        paper_context += f"Authors: {paper.authors}\n"
    if paper.year:
        paper_context += f"Year: {paper.year}\n"
    paper_context += f"Pages: {paper.page_count or 'unknown'}\n"
    paper_context += f"Status: {paper.status}\n"

    system_prompt = SYSTEM_PROMPT.format(paper_context=paper_context)

    # Build messages for LLM
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in req.messages:
        llm_messages.append({"role": msg.role, "content": msg.content})

    # Agentic tool-calling loop
    ai_client = AIClient()
    tool_calls_made = []
    max_iterations = 6

    for _ in range(max_iterations):
        # Call LLM with tools
        payload = {
            "model": settings.ai_model_fast,
            "messages": llm_messages,
            "temperature": 0.3,
            "max_tokens": 4096,
            "tools": TOOLS,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{ai_client.base_url}/chat/completions",
                    json=payload,
                    headers=ai_client._headers(),
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error(f"Assistant LLM call failed: {e}")
            raise HTTPException(status_code=502, detail="AI service unavailable")

        choice = data["choices"][0]
        message = choice["message"]

        # Check if the model wants to call tools
        if message.get("tool_calls"):
            # Append assistant message with tool calls
            llm_messages.append(message)

            for tc in message["tool_calls"]:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                tool_calls_made.append(fn_name)
                logger.info(f"Assistant tool call: {fn_name}({fn_args})")

                result = await execute_tool(fn_name, fn_args, paper_id, db)

                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # Continue loop to let LLM process tool results
            continue

        # No tool calls — final response
        final_content = message.get("content", "")
        if not final_content:
            final_content = "I wasn't able to generate a response. Please try rephrasing your question."

        return ChatResponse(message=final_content, tool_calls_made=tool_calls_made)

    # Max iterations reached
    last_content = llm_messages[-1].get("content", "") if llm_messages else ""
    return ChatResponse(
        message=last_content or "I used too many tool calls. Please ask a more specific question.",
        tool_calls_made=tool_calls_made,
    )


import httpx  # noqa: E402 (already imported at top, needed for the endpoint)
