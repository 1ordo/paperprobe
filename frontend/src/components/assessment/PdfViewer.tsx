"use client";

import { useState, useEffect, useRef } from "react";
import { getPaperSections, getToken } from "@/lib/api";
import {
  ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Loader2, FileX,
  FileText, Eye,
} from "lucide-react";

interface PdfViewerProps {
  paperId: string;
  fileType: string;
  targetPage: number | null;
  highlightText: string | null;
}

export function PdfViewer({ paperId, fileType, targetPage, highlightText }: PdfViewerProps) {
  const [viewMode, setViewMode] = useState<"pdf" | "text">("pdf");
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale, setScale] = useState(1.2);
  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [rendering, setRendering] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [sections, setSections] = useState<any[]>([]);
  const [sectionsLoading, setSectionsLoading] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function loadPdf() {
      try {
        const pdfjsLib = await import("pdfjs-dist");
        pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`;
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "/api";
        const url = `${apiBase}/papers/${paperId}/file`;
        const token = getToken();
        const doc = await pdfjsLib.getDocument({
          url,
          httpHeaders: token ? { Authorization: `Bearer ${token}` } : undefined,
        }).promise;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
      } catch (e) {
        console.error("PDF load failed:", e);
        setLoadError(true);
      }
    }
    if (fileType === "pdf") {
      loadPdf();
    }
  }, [paperId, fileType]);

  useEffect(() => {
    async function renderPage() {
      if (!pdfDoc || !canvasRef.current || rendering) return;
      setRendering(true);
      try {
        const page = await pdfDoc.getPage(currentPage);
        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext("2d")!;
        await page.render({ canvasContext: ctx, viewport }).promise;
      } catch (e) {
        console.error("Render failed:", e);
      } finally {
        setRendering(false);
      }
    }
    renderPage();
  }, [pdfDoc, currentPage, scale]);

  useEffect(() => {
    if (targetPage && targetPage !== currentPage && targetPage <= numPages) {
      setCurrentPage(targetPage);
    }
  }, [targetPage]);

  // Load sections when switching to text view
  useEffect(() => {
    if (viewMode === "text" && sections.length === 0 && !sectionsLoading) {
      setSectionsLoading(true);
      getPaperSections(paperId)
        .then((s) => setSections(s))
        .catch((e) => console.error("Failed to load sections:", e))
        .finally(() => setSectionsLoading(false));
    }
  }, [viewMode, paperId]);

  if (fileType !== "pdf") {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-tertiary gap-3">
        <FileX className="w-8 h-8" />
        <p className="text-sm">Preview not available for .{fileType} files</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="bg-surface-1 border-b border-border px-3 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-1">
          {/* View mode toggle */}
          <div className="flex gap-0.5 bg-surface-3 rounded-md p-0.5 mr-2">
            <button
              onClick={() => setViewMode("pdf")}
              className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-all ${
                viewMode === "pdf"
                  ? "bg-accent text-white shadow-sm"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
            >
              <Eye className="w-3 h-3" />
              PDF
            </button>
            <button
              onClick={() => setViewMode("text")}
              className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-all ${
                viewMode === "text"
                  ? "bg-accent text-white shadow-sm"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
            >
              <FileText className="w-3 h-3" />
              Text
            </button>
          </div>

          {viewMode === "pdf" && (
            <>
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage <= 1}
                className="p-1.5 rounded-md hover:bg-surface-3 text-text-secondary disabled:text-text-tertiary/30 disabled:hover:bg-transparent transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <div className="px-2 min-w-[80px] text-center">
                <span className="text-xs font-mono text-text-secondary">
                  {currentPage}
                  <span className="text-text-tertiary"> / {numPages || "..."}</span>
                </span>
              </div>
              <button
                onClick={() => setCurrentPage(Math.min(numPages, currentPage + 1))}
                disabled={currentPage >= numPages}
                className="p-1.5 rounded-md hover:bg-surface-3 text-text-secondary disabled:text-text-tertiary/30 disabled:hover:bg-transparent transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
        {viewMode === "pdf" && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setScale(Math.max(0.5, scale - 0.2))}
              className="p-1.5 rounded-md hover:bg-surface-3 text-text-secondary transition-colors"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-[11px] font-mono text-text-tertiary w-10 text-center">
              {Math.round(scale * 100)}%
            </span>
            <button
              onClick={() => setScale(Math.min(3, scale + 0.2))}
              className="p-1.5 rounded-md hover:bg-surface-3 text-text-secondary transition-colors"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Content area */}
      {viewMode === "pdf" ? (
        <div ref={containerRef} className="flex-1 overflow-auto flex justify-center p-6 bg-surface-0">
          {loadError ? (
            <div className="flex flex-col items-center justify-center text-text-tertiary gap-3">
              <FileX className="w-8 h-8" />
              <p className="text-sm">Failed to load PDF</p>
            </div>
          ) : pdfDoc ? (
            <canvas
              ref={canvasRef}
              className="shadow-2xl rounded-sm"
              style={{ maxWidth: "100%" }}
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-6 h-6 text-accent animate-spin" />
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-auto p-6 bg-surface-0">
          {sectionsLoading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="w-5 h-5 text-accent animate-spin" />
            </div>
          ) : sections.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 text-text-tertiary gap-2">
              <FileText className="w-6 h-6" />
              <p className="text-sm">No parsed text available</p>
            </div>
          ) : (
            <div className="space-y-6 max-w-3xl mx-auto">
              {sections.map((section) => (
                <div key={section.id} className="animate-fade-in">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[10px] font-mono text-accent uppercase tracking-wider bg-accent/10 px-1.5 py-0.5 rounded">
                      {section.section_type}
                    </span>
                    {section.page_start && (
                      <span className="text-[10px] font-mono text-text-tertiary">
                        pp. {section.page_start}
                        {section.page_end && section.page_end !== section.page_start
                          ? `–${section.page_end}`
                          : ""}
                      </span>
                    )}
                  </div>
                  {section.heading && section.heading !== "Full Document" && (
                    <h3 className="text-sm font-semibold text-text-primary mb-2">
                      {section.heading}
                    </h3>
                  )}
                  <div className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap font-mono bg-surface-1 rounded-lg border border-border p-4">
                    {section.content}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Evidence highlight bar */}
      {highlightText && (
        <div className="bg-cosmin-doubtful/10 border-t border-cosmin-doubtful/20 px-4 py-2.5 shrink-0">
          <div className="flex items-start gap-2">
            <span className="text-[10px] font-mono text-cosmin-doubtful uppercase tracking-wider shrink-0 mt-0.5">
              Evidence
            </span>
            <p className="text-xs text-text-secondary leading-relaxed">
              &ldquo;{highlightText.slice(0, 200)}
              {highlightText.length > 200 ? "..." : ""}&rdquo;
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
