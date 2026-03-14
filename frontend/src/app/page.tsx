"use client";

import { useState, useEffect } from "react";
import { getProjects, createProject } from "@/lib/api";
import type { Project } from "@/types";
import { Plus, FolderOpen, FileText, ChevronRight, X, Loader2 } from "lucide-react";

export default function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    try {
      const data = await getProjects();
      setProjects(data);
      setError(null);
    } catch (e: any) {
      console.error("Failed to load projects:", e);
      setError("Failed to connect to API. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || creating) return;
    setCreating(true);
    try {
      await createProject({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setName("");
      setDescription("");
      setShowCreate(false);
      await loadProjects();
    } catch (e) {
      console.error("Failed to create project:", e);
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="space-y-4 animate-pulse">
          <div className="h-7 bg-surface-3 rounded-md w-48" />
          <div className="h-4 bg-surface-2 rounded w-72" />
          <div className="mt-8 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-surface-2 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex items-start justify-between mb-10">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="text-text-secondary text-sm mt-1.5">
            Manage COSMIN Risk of Bias assessments for systematic reviews
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 bg-accent hover:bg-accent-hover text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-all hover:shadow-glow active:scale-[0.98]"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {error && (
        <div className="mb-6 px-4 py-3 rounded-lg bg-cosmin-inadequate/10 border border-cosmin-inadequate/20 text-cosmin-inadequate text-sm animate-fade-in">
          {error}
        </div>
      )}

      {/* Create Project Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowCreate(false)}
          />
          <div className="relative bg-surface-2 border border-border rounded-xl p-6 w-full max-w-md shadow-2xl animate-slide-up">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">Create Project</h2>
              <button
                onClick={() => setShowCreate(false)}
                className="p-1 rounded-md hover:bg-surface-4 text-text-tertiary hover:text-text-primary transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5 uppercase tracking-wider">
                  Project Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-surface-1 border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent transition-colors"
                  placeholder="e.g., Systematic Review — Chronic Pain PROMs"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5 uppercase tracking-wider">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-surface-1 border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent transition-colors resize-none"
                  rows={3}
                  placeholder="Brief description of the review scope..."
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={!name.trim() || creating}
                  className="flex-1 flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:hover:bg-accent text-white py-2.5 rounded-lg text-sm font-medium transition-all"
                >
                  {creating ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Plus className="w-4 h-4" />
                  )}
                  {creating ? "Creating..." : "Create Project"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2.5 rounded-lg text-sm text-text-secondary border border-border hover:bg-surface-3 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Project List */}
      {projects.length === 0 && !error ? (
        <div className="text-center py-20 animate-fade-in">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-surface-2 border border-border mb-5">
            <FolderOpen className="w-7 h-7 text-text-tertiary" />
          </div>
          <h3 className="text-lg font-medium text-text-primary mb-2">No projects yet</h3>
          <p className="text-text-secondary text-sm max-w-sm mx-auto">
            Create a project to begin uploading papers and running COSMIN assessments.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {projects.map((project, i) => (
            <a
              key={project.id}
              href={`/projects/${project.id}`}
              className="group block bg-surface-1 hover:bg-surface-2 border border-border hover:border-border-focus/30 rounded-xl p-5 transition-all animate-fade-in"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="flex items-center justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                      <FolderOpen className="w-4 h-4 text-accent" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-medium text-[15px] text-text-primary group-hover:text-white transition-colors truncate">
                        {project.name}
                      </h3>
                      {project.description && (
                        <p className="text-text-tertiary text-sm mt-0.5 truncate">
                          {project.description}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 shrink-0 ml-4">
                  <div className="text-right">
                    <div className="flex items-center gap-1.5 text-sm text-text-secondary">
                      <FileText className="w-3.5 h-3.5" />
                      <span className="font-mono text-xs">
                        {project.paper_count}
                      </span>
                    </div>
                    <div className="text-[11px] text-text-tertiary font-mono mt-0.5">
                      {new Date(project.created_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-text-tertiary group-hover:text-text-secondary transition-colors" />
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
