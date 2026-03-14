"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  getPaper, getAssessment, getCosminBoxes,
  triggerAnalysis, getExportUrl,
} from "@/lib/api";
import type { Paper, Assessment, CosminBox } from "@/types";
import { PdfViewer } from "@/components/assessment/PdfViewer";
import { ChecklistPanel } from "@/components/assessment/ChecklistPanel";
import { AnalysisProgress } from "@/components/assessment/AnalysisProgress";
import {
  ArrowLeft, Play, Download, FileSpreadsheet,
  Loader2, RotateCcw,
} from "lucide-react";

export default function PaperPage() {
  const params = useParams();
  const paperId = params.id as string;
  const [paper, setPaper] = useState<Paper | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [boxes, setBoxes] = useState<CosminBox[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [highlightPage, setHighlightPage] = useState<number | null>(null);
  const [highlightText, setHighlightText] = useState<string | null>(null);
  const [highlightKey, setHighlightKey] = useState(0);

  const loadData = useCallback(async () => {
    try {
      const [p, b] = await Promise.all([getPaper(paperId), getCosminBoxes()]);
      setPaper(p);
      setBoxes(b);

      // Auto-detect if analysis is currently running
      if (p.status === "analyzing") {
        setAnalyzing(true);
      }

      try {
        const a = await getAssessment(paperId);
        setAssessment(a);
      } catch {
        // No assessment yet
      }
    } catch (e) {
      console.error("Failed to load:", e);
    } finally {
      setLoading(false);
    }
  }, [paperId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleAnalyze() {
    try {
      setAnalyzing(true);
      await triggerAnalysis(paperId);
    } catch (e) {
      console.error("Analysis trigger failed:", e);
      setAnalyzing(false);
    }
  }

  function handleAnalysisComplete() {
    setAnalyzing(false);
    loadData();
  }

  function handleEvidenceClick(pageNumber: number | null, text: string) {
    if (pageNumber) setHighlightPage(pageNumber);
    setHighlightText(text);
    setHighlightKey((k) => k + 1); // force re-trigger even if same evidence clicked twice
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-56px)] bg-surface-0">
        <Loader2 className="w-6 h-6 text-accent animate-spin" />
      </div>
    );
  }

  if (!paper) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-56px)] bg-surface-0">
        <p className="text-cosmin-inadequate text-sm">Paper not found.</p>
      </div>
    );
  }

  const isAnalyzable = ["parsed", "embedded", "analyzed", "analysis_failed"].includes(paper.status);
  const hasAssessment = assessment && (assessment.standard_ratings?.length > 0 || assessment.box_ratings?.length > 0);

  return (
    <div className="h-[calc(100vh-56px)] flex flex-col bg-surface-0">
      {/* Paper toolbar */}
      <div className="bg-surface-1 border-b border-border px-4 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <a
            href={`/projects/${paper.project_id}`}
            className="p-1.5 rounded-md hover:bg-surface-3 text-text-tertiary hover:text-text-primary transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </a>
          <div className="h-5 w-px bg-border" />
          <div className="min-w-0">
            <h1 className="font-medium text-sm text-text-primary truncate">
              {paper.title || paper.filename}
            </h1>
            <div className="flex items-center gap-2 text-[11px] text-text-tertiary font-mono">
              {paper.authors && <span className="truncate max-w-[300px]">{paper.authors}</span>}
              {paper.year && <span>({paper.year})</span>}
              {paper.page_count && <span>{paper.page_count}pp</span>}
              <span className={`px-1.5 py-px rounded text-[10px] font-bold uppercase ${
                paper.status === "analyzed" ? "bg-cosmin-very_good/10 text-cosmin-very_good"
                : paper.status === "analyzing" ? "bg-accent/10 text-accent"
                : paper.status === "parsed" ? "bg-cosmin-adequate/10 text-cosmin-adequate"
                : paper.status === "analysis_failed" ? "bg-cosmin-inadequate/10 text-cosmin-inadequate"
                : "bg-surface-3 text-text-tertiary"
              }`}>
                {paper.status}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {hasAssessment && (
            <>
              <a
                href={getExportUrl(paperId, "xlsx")}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-cosmin-very_good/10 text-cosmin-very_good hover:bg-cosmin-very_good/20 transition-colors"
              >
                <FileSpreadsheet className="w-3 h-3" />
                Excel
              </a>
              <a
                href={getExportUrl(paperId, "csv")}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border text-text-secondary hover:bg-surface-3 transition-colors"
              >
                <Download className="w-3 h-3" />
                CSV
              </a>
            </>
          )}
          {hasAssessment && !analyzing && (
            <button
              onClick={handleAnalyze}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border text-text-secondary hover:bg-surface-3 transition-colors"
              title="Re-run analysis"
            >
              <RotateCcw className="w-3 h-3" />
              Re-analyze
            </button>
          )}
          {isAnalyzable && !analyzing && !hasAssessment && (
            <button
              onClick={handleAnalyze}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-accent hover:bg-accent-hover text-white transition-all hover:shadow-glow"
            >
              <Play className="w-3 h-3" />
              Run COSMIN Analysis
            </button>
          )}
        </div>
      </div>

      {/* Split panel */}
      <div className="flex-1 flex overflow-hidden">
        <div className="w-1/2 border-r border-border overflow-auto bg-surface-0">
          <PdfViewer
            paperId={paperId}
            fileType={paper.file_type}
            targetPage={highlightPage}
            highlightText={highlightText}
            highlightKey={highlightKey}
          />
        </div>
        <div className="w-1/2 overflow-auto bg-surface-1">
          {analyzing ? (
            <AnalysisProgress
              paperId={paperId}
              onComplete={handleAnalysisComplete}
            />
          ) : (
            <ChecklistPanel
              paper={paper}
              assessment={assessment}
              boxes={boxes}
              onEvidenceClick={handleEvidenceClick}
              onRefresh={loadData}
            />
          )}
        </div>
      </div>
    </div>
  );
}
