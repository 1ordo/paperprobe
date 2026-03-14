"use client";

import { useState } from "react";
import type { Paper, Assessment, CosminBox, StandardRating, Rating } from "@/types";
import { RATING_COLORS, RATING_LABELS } from "@/types";
import { RatingEditor } from "./RatingEditor";
import {
  ChevronDown, ChevronRight, ClipboardCheck, Pen,
  Sparkles, BookOpen, AlertTriangle,
} from "lucide-react";

interface ChecklistPanelProps {
  paper: Paper;
  assessment: Assessment | null;
  boxes: CosminBox[];
  onEvidenceClick: (page: number | null, text: string) => void;
  onRefresh: () => void;
}

function RatingBadge({ rating, size = "sm" }: { rating: Rating | null | undefined; size?: "sm" | "xs" }) {
  if (!rating) return <span className="text-[11px] text-text-tertiary font-mono">--</span>;
  const color = RATING_COLORS[rating] || "#6b7280";
  const pad = size === "sm" ? "px-2 py-0.5" : "px-1.5 py-px";
  return (
    <span
      className={`inline-flex items-center ${pad} rounded text-[10px] font-bold tracking-wide uppercase`}
      style={{ backgroundColor: `${color}20`, color }}
    >
      {RATING_LABELS[rating] || rating}
    </span>
  );
}

function WorstScoreBadge({ rating }: { rating: string | null | undefined }) {
  if (!rating) return null;
  const color = RATING_COLORS[rating as Rating] || "#6b7280";
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase"
      style={{ backgroundColor: `${color}20`, color }}
    >
      <AlertTriangle className="w-2.5 h-2.5" />
      {RATING_LABELS[rating as Rating] || rating}
    </span>
  );
}

export function ChecklistPanel({ paper, assessment, boxes, onEvidenceClick, onRefresh }: ChecklistPanelProps) {
  const [expandedBox, setExpandedBox] = useState<number | null>(null);
  const [editingRating, setEditingRating] = useState<string | null>(null);

  const hasRatings = assessment && (assessment.standard_ratings?.length > 0 || assessment.box_ratings?.length > 0);

  if (!hasRatings) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <div className="w-14 h-14 rounded-2xl bg-surface-3 flex items-center justify-center mb-4">
          <ClipboardCheck className="w-6 h-6 text-text-tertiary" />
        </div>
        <h3 className="font-medium text-text-primary mb-1.5">No assessment yet</h3>
        <p className="text-sm text-text-tertiary max-w-xs">
          {paper.status === "uploaded"
            ? "Paper is being parsed. Please wait..."
            : paper.status === "parsed" || paper.status === "embedded"
            ? 'Click "Run COSMIN Analysis" above to evaluate this paper.'
            : paper.status === "analyzing"
            ? "AI analysis in progress. This may take a few minutes..."
            : paper.status === "analyzed"
            ? 'Click "Re-analyze" to run the analysis again with updated methodology.'
            : `Current status: ${paper.status}`}
        </p>
      </div>
    );
  }

  const ratingMap = new Map<number, StandardRating>();
  for (const r of assessment.standard_ratings) {
    ratingMap.set(r.standard_id, r);
  }

  const boxRatingMap = new Map<number, string | null>();
  for (const br of assessment.box_ratings) {
    boxRatingMap.set(br.box_id, br.ai_worst_score);
  }

  const relevantBoxNums = new Set(
    assessment.relevant_boxes?.relevant_boxes || []
  );

  return (
    <div className="h-full flex flex-col">
      {/* Summary header */}
      <div className="p-4 bg-surface-2 border-b border-border shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" />
            <h2 className="font-semibold text-sm text-text-primary">COSMIN Assessment</h2>
          </div>
          <span className="text-[10px] font-mono text-text-tertiary uppercase tracking-wider px-2 py-0.5 bg-surface-3 rounded">
            {assessment.status}
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {boxes.map((box) => {
            const isRelevant = relevantBoxNums.has(box.box_number);
            const worstScore = boxRatingMap.get(box.id);
            const isActive = expandedBox === box.box_number;
            const dotColor = worstScore ? RATING_COLORS[worstScore as Rating] : undefined;
            return (
              <button
                key={box.id}
                onClick={() => setExpandedBox(isActive ? null : box.box_number)}
                className={`text-[11px] px-2 py-1 rounded-md border font-medium transition-all ${
                  isActive
                    ? "border-accent bg-accent/10 text-accent"
                    : isRelevant
                    ? "border-border bg-surface-3 text-text-secondary hover:bg-surface-4 hover:text-text-primary"
                    : "border-transparent bg-surface-3/50 text-text-tertiary"
                }`}
              >
                <span className="font-mono">B{box.box_number}</span>
                {dotColor && (
                  <span
                    className="ml-1 inline-block w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: dotColor }}
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Box list */}
      <div className="flex-1 overflow-auto">
        {boxes.map((box) => {
          const isExpanded = expandedBox === box.box_number;
          const isRelevant = relevantBoxNums.has(box.box_number);
          const worstScore = boxRatingMap.get(box.id);

          return (
            <div key={box.id} className={`border-b border-border ${!isRelevant ? "opacity-40" : ""}`}>
              <button
                onClick={() => setExpandedBox(isExpanded ? null : box.box_number)}
                className="w-full text-left px-4 py-3 hover:bg-surface-2/50 transition-colors flex items-center justify-between gap-3"
              >
                <div className="flex items-center gap-3 min-w-0">
                  {isExpanded ? (
                    <ChevronDown className="w-3.5 h-3.5 text-accent shrink-0" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-text-tertiary shrink-0" />
                  )}
                  <div className="min-w-0">
                    <span className="text-sm font-medium text-text-primary">
                      <span className="font-mono text-text-tertiary mr-1.5">Box {box.box_number}</span>
                      {box.name}
                    </span>
                    {!isRelevant && (
                      <span className="ml-2 text-[10px] text-text-tertiary font-mono uppercase">N/A</span>
                    )}
                  </div>
                </div>
                <WorstScoreBadge rating={worstScore} />
              </button>

              {isExpanded && (
                <div className="px-4 pb-4 animate-fade-in">
                  {box.sub_boxes.map((subBox) => (
                    <div key={subBox.id} className="mb-4 last:mb-0">
                      <div className="flex items-center gap-2 mb-2.5 px-1">
                        <div className="h-px flex-1 bg-border" />
                        <h4 className="text-[10px] font-semibold text-text-tertiary uppercase tracking-widest shrink-0">
                          {subBox.sub_box_code} &middot; {subBox.name}
                        </h4>
                        <div className="h-px flex-1 bg-border" />
                      </div>
                      <div className="space-y-2">
                        {subBox.standards.map((std) => {
                          const rating = ratingMap.get(std.id);
                          return (
                            <div
                              key={std.id}
                              className="bg-surface-2 rounded-lg border border-border p-3"
                            >
                              <p className="text-[13px] text-text-primary leading-relaxed mb-2.5">
                                <span className="font-mono text-text-tertiary text-xs mr-1">
                                  {std.standard_number}.
                                </span>
                                {std.question_text}
                              </p>

                              {rating ? (
                                <>
                                  {/* Rating row */}
                                  <div className="flex items-center gap-3 text-xs mb-2 flex-wrap">
                                    <div className="flex items-center gap-1.5">
                                      <span className="text-[10px] text-text-tertiary font-mono uppercase">AI</span>
                                      <RatingBadge rating={rating.ai_rating} />
                                      {rating.ai_confidence != null && (
                                        <span className="text-[10px] text-text-tertiary font-mono">
                                          {Math.round(rating.ai_confidence * 100)}%
                                        </span>
                                      )}
                                    </div>
                                    <div className="w-px h-3 bg-border" />
                                    <div className="flex items-center gap-1.5">
                                      <span className="text-[10px] text-text-tertiary font-mono uppercase">R1</span>
                                      <RatingBadge rating={rating.reviewer1_rating} size="xs" />
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                      <span className="text-[10px] text-text-tertiary font-mono uppercase">R2</span>
                                      <RatingBadge rating={rating.reviewer2_rating} size="xs" />
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                      <span className="text-[10px] text-text-tertiary font-mono uppercase">Final</span>
                                      <RatingBadge rating={rating.final_rating} />
                                    </div>
                                    <button
                                      onClick={() =>
                                        setEditingRating(editingRating === rating.id ? null : rating.id)
                                      }
                                      className="ml-auto flex items-center gap-1 text-[11px] text-accent hover:text-accent-hover transition-colors"
                                    >
                                      <Pen className="w-3 h-3" />
                                      {editingRating === rating.id ? "Close" : "Edit"}
                                    </button>
                                  </div>

                                  {/* AI reasoning */}
                                  {rating.ai_reasoning && (
                                    <p className="text-xs text-text-tertiary bg-surface-3 rounded-md p-2.5 mb-2 leading-relaxed border border-border/50">
                                      {rating.ai_reasoning}
                                    </p>
                                  )}

                                  {/* Evidence */}
                                  {rating.evidence?.length > 0 && (
                                    <div className="space-y-1">
                                      {rating.evidence.map((ev) => (
                                        <button
                                          key={ev.id}
                                          onClick={() => onEvidenceClick(ev.page_number, ev.evidence_text)}
                                          className="group/ev block w-full text-left text-xs bg-cosmin-doubtful/5 border border-cosmin-doubtful/10 rounded-md px-2.5 py-1.5 hover:bg-cosmin-doubtful/10 transition-colors"
                                        >
                                          {ev.page_number && (
                                            <span className="font-mono text-cosmin-doubtful text-[10px] mr-1">
                                              p.{ev.page_number}
                                            </span>
                                          )}
                                          <span className="text-text-secondary group-hover/ev:text-text-primary transition-colors">
                                            &ldquo;{ev.evidence_text.slice(0, 180)}
                                            {ev.evidence_text.length > 180 ? "..." : ""}&rdquo;
                                          </span>
                                        </button>
                                      ))}
                                    </div>
                                  )}

                                  {editingRating === rating.id && (
                                    <RatingEditor
                                      rating={rating}
                                      standard={std}
                                      onSave={() => {
                                        setEditingRating(null);
                                        onRefresh();
                                      }}
                                    />
                                  )}
                                </>
                              ) : (
                                <p className="text-[11px] text-text-tertiary font-mono">Not rated</p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
