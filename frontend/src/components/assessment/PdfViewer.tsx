"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getPaperSections, getToken } from "@/lib/api";
import {
  ZoomIn, ZoomOut, Loader2, FileX,
  FileText, Eye,
} from "lucide-react";

interface PdfViewerProps {
  paperId: string;
  fileType: string;
  targetPage: number | null;
  highlightText: string | null;
  highlightKey?: number;
}

export function PdfViewer({ paperId, fileType, targetPage, highlightText, highlightKey }: PdfViewerProps) {
  const [viewMode, setViewMode] = useState<"pdf" | "text">("pdf");
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState(1.2);
  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [loadError, setLoadError] = useState(false);
  const [sections, setSections] = useState<any[]>([]);
  const [sectionsLoading, setSectionsLoading] = useState(false);
  const [pagesReady, setPagesReady] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const textLayerDivs = useRef<Map<number, HTMLDivElement>>(new Map());
  const renderingRef = useRef(false);

  // Load the PDF document
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

  // Render all pages with canvases + text layers
  const renderAllPages = useCallback(async () => {
    if (!pdfDoc || renderingRef.current) return;
    renderingRef.current = true;
    setPagesReady(false);

    const dpr = window.devicePixelRatio || 1;

    try {
      const pdfjsLib = await import("pdfjs-dist");

      for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale });
        const wrapper = pageRefs.current.get(pageNum);
        if (!wrapper) continue;

        // Set wrapper CSS dimensions to match the viewport
        wrapper.style.width = `${viewport.width}px`;
        wrapper.style.height = `${viewport.height}px`;

        // --- Canvas (retina-aware) ---
        let canvas = wrapper.querySelector("canvas") as HTMLCanvasElement | null;
        if (!canvas) {
          canvas = document.createElement("canvas");
          canvas.style.display = "block";
          wrapper.insertBefore(canvas, wrapper.firstChild);
        }
        // Render at DPR resolution for crisp text
        canvas.width = Math.floor(viewport.width * dpr);
        canvas.height = Math.floor(viewport.height * dpr);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        const ctx = canvas.getContext("2d")!;
        ctx.scale(dpr, dpr);
        await page.render({ canvasContext: ctx, viewport }).promise;

        // --- Text layer (official pdf.js API) ---
        const textDiv = textLayerDivs.current.get(pageNum);
        if (textDiv) {
          // Clear previous text layer content
          textDiv.innerHTML = "";
          textDiv.style.width = `${viewport.width}px`;
          textDiv.style.height = `${viewport.height}px`;

          const textContent = await page.getTextContent();
          const textLayer = new pdfjsLib.TextLayer({
            textContentSource: textContent,
            container: textDiv,
            viewport: viewport,
          });
          await textLayer.render();
        }
      }
      setPagesReady(true);
    } catch (e) {
      console.error("Render failed:", e);
    } finally {
      renderingRef.current = false;
    }
  }, [pdfDoc, scale]);

  useEffect(() => {
    if (pdfDoc && numPages > 0 && viewMode === "pdf") {
      // Reset the rendering lock — DOM elements are fresh after re-mount
      renderingRef.current = false;
      renderAllPages();
    }
  }, [pdfDoc, numPages, scale, viewMode, renderAllPages]);

  // Re-render canvases when tab becomes visible (browsers discard canvas on background)
  useEffect(() => {
    function handleVisibility() {
      if (document.visibilityState === "visible" && pdfDoc && numPages > 0) {
        renderingRef.current = false; // reset lock
        renderAllPages();
      }
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [pdfDoc, numPages, renderAllPages]);

  // Scroll to target page when evidence is clicked
  useEffect(() => {
    // Remove previous target highlight
    for (const [, el] of pageRefs.current) {
      el?.classList.remove("evidence-target");
    }

    if (targetPage && targetPage >= 1 && targetPage <= numPages && pagesReady) {
      const wrapper = pageRefs.current.get(targetPage);
      if (wrapper && containerRef.current) {
        wrapper.scrollIntoView({ behavior: "smooth", block: "start" });
        wrapper.classList.add("evidence-target");
      }
    }
  }, [targetPage, highlightKey, numPages, pagesReady]);

  // Highlight evidence text in text layers
  useEffect(() => {
    // Clear all previous highlights
    for (const [, textDiv] of textLayerDivs.current) {
      if (!textDiv) continue;
      textDiv.querySelectorAll(".evidence-highlight").forEach((el) =>
        el.classList.remove("evidence-highlight")
      );
    }

    if (!highlightText || highlightText.length < 8 || !pagesReady) return;

    // Normalize helper: collapse whitespace, strip punctuation variations, lowercase
    function normalize(s: string) {
      return s
        .replace(/[\u2018\u2019\u201C\u201D]/g, "'")  // curly quotes → straight
        .replace(/[\u2013\u2014]/g, "-")               // em/en dash → hyphen
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();
    }

    // Extract significant words (3+ chars) for word-level fallback matching
    function extractWords(s: string): string[] {
      return normalize(s)
        .split(/\s+/)
        .filter((w) => w.length >= 3)
        .map((w) => w.replace(/^[^a-z0-9]+|[^a-z0-9]+$/gi, "")) // strip surrounding punctuation
        .filter((w) => w.length >= 3);
    }

    const searchNorm = normalize(highlightText);

    // Determine which pages to search first
    const pagePriority: number[] = [];
    if (targetPage && targetPage >= 1 && targetPage <= numPages) {
      pagePriority.push(targetPage);
      if (targetPage > 1) pagePriority.push(targetPage - 1);
      if (targetPage < numPages) pagePriority.push(targetPage + 1);
    }
    for (let i = 1; i <= numPages; i++) {
      if (!pagePriority.includes(i)) pagePriority.push(i);
    }

    for (const pageNum of pagePriority) {
      const textDiv = textLayerDivs.current.get(pageNum);
      if (!textDiv) continue;

      const spans = Array.from(textDiv.querySelectorAll("span"));
      if (spans.length === 0) continue;

      // Build concatenated text with span position tracking
      const entries: { span: Element; text: string; start: number }[] = [];
      let accumulated = "";
      for (const span of spans) {
        const raw = span.textContent || "";
        const start = accumulated.length;
        accumulated += raw;
        entries.push({ span, text: raw, start });
      }

      const fullNorm = normalize(accumulated);

      // --- Strategy 1: Substring match with progressively shorter snippets ---
      let matchIdx = -1;
      let matchLen = 0;
      const maxSnippet = Math.min(searchNorm.length, 120);
      for (let tryLen = maxSnippet; tryLen >= 15; tryLen -= 5) {
        const trySnippet = searchNorm.slice(0, tryLen);
        matchIdx = fullNorm.indexOf(trySnippet);
        if (matchIdx !== -1) {
          matchLen = trySnippet.length;
          break;
        }
      }

      // --- Strategy 2: Word-sequence matching (handles text extraction differences) ---
      if (matchIdx === -1) {
        const searchWords = extractWords(highlightText);
        if (searchWords.length >= 3) {
          // Try to find a consecutive sequence of words from the evidence in the page
          const pageWords = extractWords(accumulated);
          // Use first 8 significant words to find the region
          const needle = searchWords.slice(0, Math.min(8, searchWords.length));

          // Sliding window: find best match position
          let bestScore = 0;
          let bestStart = -1;
          let bestEnd = -1;

          for (let i = 0; i <= pageWords.length - needle.length; i++) {
            let score = 0;
            for (let j = 0; j < needle.length; j++) {
              if (pageWords[i + j] === needle[j]) score++;
              else if (pageWords[i + j]?.includes(needle[j]) || needle[j]?.includes(pageWords[i + j])) score += 0.5;
            }
            if (score > bestScore && score >= needle.length * 0.6) {
              bestScore = score;
              bestStart = i;
              bestEnd = i + needle.length;
            }
          }

          if (bestStart !== -1) {
            // Map matched word positions back to spans
            // Find these words in the accumulated text and highlight containing spans
            const matchedWords = new Set(pageWords.slice(bestStart, bestEnd));
            let firstHighlighted: Element | null = null;

            for (const entry of entries) {
              const spanNorm = normalize(entry.text);
              const spanWords = spanNorm.split(/\s+/).filter((w) => w.length >= 3);
              const hasMatch = spanWords.some((w) => {
                const cleaned = w.replace(/^[^a-z0-9]+|[^a-z0-9]+$/gi, "");
                return matchedWords.has(cleaned);
              });
              if (hasMatch) {
                entry.span.classList.add("evidence-highlight");
                if (!firstHighlighted) firstHighlighted = entry.span;
              }
            }

            if (firstHighlighted) {
              firstHighlighted.scrollIntoView({ behavior: "smooth", block: "center" });
              return;
            }
          }
        }
        continue; // No match on this page
      }

      // --- Map substring match region back to spans ---
      // Build raw→normalized position mapping
      let normPos = 0;
      const rawToNorm: number[] = [];
      let prevWasSpace = false;
      for (const ch of accumulated) {
        const isSpace = /\s/.test(ch);
        if (isSpace) {
          if (!prevWasSpace) {
            rawToNorm.push(normPos);
            normPos++;
          } else {
            rawToNorm.push(normPos);
          }
          prevWasSpace = true;
        } else {
          rawToNorm.push(normPos);
          normPos++;
          prevWasSpace = false;
        }
      }

      const matchEnd = matchIdx + matchLen;
      let firstHighlighted: Element | null = null;

      for (const entry of entries) {
        const spanStart = entry.start;
        const spanEnd = spanStart + entry.text.length;
        let overlaps = false;
        for (let i = spanStart; i < spanEnd && i < rawToNorm.length; i++) {
          if (rawToNorm[i] >= matchIdx && rawToNorm[i] < matchEnd) {
            overlaps = true;
            break;
          }
        }
        if (overlaps) {
          entry.span.classList.add("evidence-highlight");
          if (!firstHighlighted) firstHighlighted = entry.span;
        }
      }

      if (firstHighlighted) {
        firstHighlighted.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
    }
  }, [highlightText, highlightKey, targetPage, numPages, pagesReady]);

  // Clear stale DOM refs when leaving PDF view so re-mount gets fresh ones
  useEffect(() => {
    if (viewMode === "text") {
      pageRefs.current.clear();
      textLayerDivs.current.clear();
    }
  }, [viewMode]);

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

          {viewMode === "pdf" && numPages > 0 && (
            <span className="text-xs font-mono text-text-tertiary ml-1">
              {numPages} pages
            </span>
          )}
        </div>
        {viewMode === "pdf" && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setScale(Math.max(0.5, +(scale - 0.2).toFixed(1)))}
              className="p-1.5 rounded-md hover:bg-surface-3 text-text-secondary transition-colors"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-[11px] font-mono text-text-tertiary w-10 text-center">
              {Math.round(scale * 100)}%
            </span>
            <button
              onClick={() => setScale(Math.min(3, +(scale + 0.2).toFixed(1)))}
              className="p-1.5 rounded-md hover:bg-surface-3 text-text-secondary transition-colors"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Content area */}
      {viewMode === "pdf" ? (
        <div ref={containerRef} className="flex-1 overflow-auto bg-surface-0">
          {loadError ? (
            <div className="flex flex-col items-center justify-center h-full text-text-tertiary gap-3">
              <FileX className="w-8 h-8" />
              <p className="text-sm">Failed to load PDF</p>
            </div>
          ) : pdfDoc ? (
            <div className="flex flex-col items-center gap-3 py-4 px-6">
              {Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
                <div
                  key={pageNum}
                  ref={(el) => { if (el) pageRefs.current.set(pageNum, el); }}
                  className="pdf-page-wrapper shadow-2xl rounded-sm bg-white shrink-0"
                >
                  {/* Canvas is inserted here imperatively */}
                  <div
                    ref={(el) => { if (el) textLayerDivs.current.set(pageNum, el); }}
                    className="textLayer"
                  />
                </div>
              ))}
            </div>
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
    </div>
  );
}
