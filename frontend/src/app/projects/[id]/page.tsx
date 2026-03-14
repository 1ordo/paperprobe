"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { getProject, getProjectPapers, uploadPaper } from "@/lib/api";
import type { Project, Paper } from "@/types";
import {
  ArrowLeft, Upload, FileText, ChevronRight, Loader2,
  CheckCircle2, AlertCircle, Clock, Cpu, Search,
} from "lucide-react";

const STATUS_CONFIG: Record<string, { label: string; icon: any; color: string; bg: string }> = {
  uploaded: { label: "Uploaded", icon: Clock, color: "text-text-tertiary", bg: "bg-surface-3" },
  parsing: { label: "Parsing", icon: Loader2, color: "text-cosmin-doubtful", bg: "bg-cosmin-doubtful/10" },
  parsed: { label: "Parsed", icon: CheckCircle2, color: "text-cosmin-adequate", bg: "bg-cosmin-adequate/10" },
  embedded: { label: "Indexed", icon: Search, color: "text-cosmin-adequate", bg: "bg-cosmin-adequate/10" },
  analyzing: { label: "Analyzing", icon: Cpu, color: "text-accent", bg: "bg-accent/10" },
  analyzed: { label: "Analyzed", icon: CheckCircle2, color: "text-cosmin-very_good", bg: "bg-cosmin-very_good/10" },
  parse_failed: { label: "Failed", icon: AlertCircle, color: "text-cosmin-inadequate", bg: "bg-cosmin-inadequate/10" },
  analysis_failed: { label: "Failed", icon: AlertCircle, color: "text-cosmin-inadequate", bg: "bg-cosmin-inadequate/10" },
};

export default function ProjectPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [proj, paps] = await Promise.all([
        getProject(projectId),
        getProjectPapers(projectId),
      ]);
      setProject(proj);
      setPapers(paps);
    } catch (e) {
      console.error("Failed to load:", e);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleUpload(files: FileList | null) {
    if (!files) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        await uploadPaper(projectId, file);
      }
      await loadData();
    } catch (e) {
      console.error("Upload failed:", e);
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-16">
        <div className="space-y-4 animate-pulse">
          <div className="h-5 bg-surface-3 rounded w-24" />
          <div className="h-8 bg-surface-3 rounded-md w-64" />
          <div className="h-4 bg-surface-2 rounded w-96" />
          <div className="mt-8 h-40 bg-surface-2 rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      {/* Back link */}
      <a
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-text-tertiary hover:text-text-primary transition-colors mb-6"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        All Projects
      </a>

      {/* Project header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">{project?.name}</h1>
        {project?.description && (
          <p className="text-text-secondary text-sm mt-1.5">{project.description}</p>
        )}
        <div className="flex items-center gap-4 mt-3 text-xs text-text-tertiary font-mono">
          <span>{papers.length} paper{papers.length !== 1 ? "s" : ""}</span>
          {project?.created_at && (
            <span>Created {new Date(project.created_at).toLocaleDateString()}</span>
          )}
        </div>
      </div>

      {/* Upload Zone */}
      <div
        className={`relative border-2 border-dashed rounded-xl p-10 text-center mb-8 transition-all ${
          dragOver
            ? "border-accent bg-accent/5"
            : "border-border hover:border-surface-4"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-surface-2 border border-border mb-4">
          {uploading ? (
            <Loader2 className="w-5 h-5 text-accent animate-spin" />
          ) : (
            <Upload className="w-5 h-5 text-text-tertiary" />
          )}
        </div>
        <p className="text-text-secondary text-sm mb-3">
          {uploading ? "Uploading files..." : "Drop PDF or DOCX files here, or click to browse"}
        </p>
        <label className="inline-flex items-center gap-2 bg-surface-3 hover:bg-surface-4 border border-border text-text-primary px-4 py-2 rounded-lg cursor-pointer text-sm font-medium transition-colors">
          <Upload className="w-3.5 h-3.5" />
          Browse Files
          <input
            type="file"
            accept=".pdf,.docx"
            multiple
            className="hidden"
            onChange={(e) => handleUpload(e.target.files)}
            disabled={uploading}
          />
        </label>
      </div>

      {/* Papers List */}
      {papers.length === 0 ? (
        <div className="text-center py-16 bg-surface-1 rounded-xl border border-border">
          <FileText className="w-8 h-8 text-text-tertiary mx-auto mb-3" />
          <p className="text-text-secondary text-sm">No papers uploaded yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {papers.map((paper, i) => {
            const status = STATUS_CONFIG[paper.status] || STATUS_CONFIG.uploaded;
            const StatusIcon = status.icon;
            const isSpinning = ["parsing", "analyzing"].includes(paper.status);
            return (
              <a
                key={paper.id}
                href={`/paper/${paper.id}`}
                className="group flex items-center gap-4 bg-surface-1 hover:bg-surface-2 border border-border hover:border-border-focus/30 rounded-xl p-4 transition-all animate-fade-in"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <div className="w-10 h-10 rounded-lg bg-surface-3 flex items-center justify-center shrink-0">
                  <FileText className="w-4.5 h-4.5 text-text-tertiary" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-sm text-text-primary group-hover:text-white transition-colors truncate">
                    {paper.title || paper.filename}
                  </h3>
                  <div className="flex items-center gap-3 mt-1 text-xs text-text-tertiary font-mono">
                    {paper.authors && (
                      <span className="truncate max-w-[200px]">{paper.authors}</span>
                    )}
                    {paper.year && <span>{paper.year}</span>}
                    {paper.page_count && <span>{paper.page_count}pp</span>}
                  </div>
                </div>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium ${status.bg} ${status.color}`}>
                  <StatusIcon className={`w-3 h-3 ${isSpinning ? "animate-spin" : ""}`} />
                  {status.label}
                </div>
                <ChevronRight className="w-4 h-4 text-text-tertiary group-hover:text-text-secondary shrink-0 transition-colors" />
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
