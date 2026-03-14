"use client";

import { useState, useEffect } from "react";
import { getAnalysisStatus } from "@/lib/api";
import {
  Cpu, Database, Search, Brain, CheckCircle2, XCircle,
  Loader2, Sparkles, Clock,
} from "lucide-react";

interface AnalysisProgressProps {
  paperId: string;
  onComplete: () => void;
}

const PIPELINE_STEPS = [
  { key: "embedding", label: "Embedding document", desc: "Creating vector representations of document chunks", icon: Database, threshold: 0.05 },
  { key: "relevance", label: "Relevance classification", desc: "Determining which COSMIN boxes apply to this paper", icon: Search, threshold: 0.05 },
  { key: "initializing", label: "Initializing pipeline", desc: "Loading COSMIN standards and preparing agents", icon: Cpu, threshold: 0.15 },
  { key: "extracting", label: "Extracting evidence", desc: "Retrieving and analyzing methodological evidence from the paper", icon: Brain, threshold: 0.15 },
  { key: "rating", label: "Rating standards", desc: "AI agents evaluating each standard per applicable COSMIN box", icon: Sparkles, threshold: 0.25 },
  { key: "storing", label: "Storing ratings", desc: "Saving individual standard ratings and evidence to database", icon: Database, threshold: 0.50 },
  { key: "synthesizing", label: "Synthesizing results", desc: "Validating consistency and computing worst-score-counts", icon: Brain, threshold: 0.80 },
  { key: "done", label: "Analysis complete", desc: "All COSMIN boxes have been evaluated", icon: CheckCircle2, threshold: 1.0 },
];

export function AnalysisProgress({ paperId, onComplete }: AnalysisProgressProps) {
  const [step, setStep] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [startTime] = useState(Date.now());

  useEffect(() => {
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [startTime]);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const status = await getAnalysisStatus(paperId);
        const latestTask = status.tasks?.find((t: any) => t.task_type === "analyze");
        if (!latestTask) return;

        if (latestTask.step) setStep(latestTask.step);
        if (latestTask.progress != null) setProgress(latestTask.progress);

        if (latestTask.status === "completed" || status.paper_status === "analyzed") {
          setStep("done");
          setProgress(1);
          setTimeout(onComplete, 1200);
          return;
        }
        if (latestTask.status === "failed") {
          setError(latestTask.error_message || "Analysis failed");
          return;
        }
      } catch {
        // ignore
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [paperId, onComplete]);

  const currentStepIndex = PIPELINE_STEPS.findIndex((s) => s.key === step);
  const formatTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 animate-fade-in">
      <div className="w-full max-w-md space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-accent/10 border border-accent/20 mb-2">
            {error ? (
              <XCircle className="w-7 h-7 text-cosmin-inadequate" />
            ) : step === "done" ? (
              <CheckCircle2 className="w-7 h-7 text-cosmin-very_good" />
            ) : (
              <Cpu className="w-7 h-7 text-accent animate-pulse" />
            )}
          </div>
          <h2 className="text-lg font-semibold text-text-primary">
            {error ? "Analysis Failed" : step === "done" ? "Analysis Complete" : "COSMIN Analysis Running"}
          </h2>
          <p className="text-xs text-text-tertiary font-mono">
            {error ? "" : `Elapsed: ${formatTime(elapsed)}`}
          </p>
        </div>

        {/* Error display */}
        {error && (
          <div className="bg-cosmin-inadequate/10 border border-cosmin-inadequate/20 rounded-xl p-4">
            <p className="text-xs text-cosmin-inadequate font-mono leading-relaxed">{error}</p>
          </div>
        )}

        {/* Progress bar */}
        {!error && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-text-secondary">{Math.round(progress * 100)}%</span>
              <span className="text-text-tertiary">
                {step === "done" ? "Complete" : step || "Starting..."}
              </span>
            </div>
            <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${Math.max(progress * 100, 2)}%`,
                  background: step === "done"
                    ? "#92D050"
                    : "linear-gradient(90deg, #3b82f6, #60a5fa)",
                }}
              />
            </div>
          </div>
        )}

        {/* Pipeline steps */}
        {!error && (
          <div className="space-y-1">
            {PIPELINE_STEPS.map((s, i) => {
              const isActive = s.key === step;
              const isDone = currentStepIndex > i || step === "done";
              const isPending = currentStepIndex < i && step !== "done";
              const StepIcon = s.icon;

              return (
                <div
                  key={s.key}
                  className={`flex items-start gap-3 px-3 py-2 rounded-lg transition-all duration-300 ${
                    isActive
                      ? "bg-accent/10 border border-accent/20"
                      : isDone
                      ? "bg-cosmin-very_good/5 border border-transparent"
                      : "border border-transparent opacity-40"
                  }`}
                >
                  <div className="mt-0.5 shrink-0">
                    {isDone ? (
                      <CheckCircle2 className="w-4 h-4 text-cosmin-very_good" />
                    ) : isActive ? (
                      <Loader2 className="w-4 h-4 text-accent animate-spin" />
                    ) : (
                      <Clock className="w-4 h-4 text-text-tertiary" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className={`text-xs font-medium ${
                      isActive ? "text-accent" : isDone ? "text-cosmin-very_good" : "text-text-tertiary"
                    }`}>
                      {s.label}
                    </p>
                    {(isActive || isDone) && (
                      <p className="text-[11px] text-text-tertiary mt-0.5 leading-relaxed">
                        {s.desc}
                      </p>
                    )}
                  </div>
                  <StepIcon className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${
                    isActive ? "text-accent" : isDone ? "text-cosmin-very_good/50" : "text-text-tertiary/30"
                  }`} />
                </div>
              );
            })}
          </div>
        )}

        {/* Model info */}
        {!error && step !== "done" && (
          <div className="text-center">
            <p className="text-[10px] text-text-tertiary font-mono">
              Model: openai/gpt-oss-120b &middot; Multi-agent pipeline
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
