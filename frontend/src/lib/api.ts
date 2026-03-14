const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

export function setToken(token: string) {
  localStorage.setItem("auth_token", token);
  document.cookie = `auth_token=${token}; path=/; max-age=${7 * 24 * 3600}; SameSite=Lax`;
}

export function clearToken() {
  localStorage.removeItem("auth_token");
  document.cookie = "auth_token=; path=/; max-age=0";
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {};

  // Only set Content-Type for non-FormData requests
  if (!(options?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  // Attach auth token
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    ...options,
    headers: { ...headers, ...(options?.headers as Record<string, string>) },
  });
  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const error = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json();
}

// Auth
export async function login(email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    throw new Error("Invalid credentials");
  }
  const data = await res.json();
  setToken(data.token);
  return data;
}

// Projects — no trailing slashes (FastAPI redirects them)
export const getProjects = () => fetchAPI<any[]>("/projects");
export const createProject = (data: { name: string; description?: string }) =>
  fetchAPI<any>("/projects", { method: "POST", body: JSON.stringify(data) });
export const getProject = (id: string) => fetchAPI<any>(`/projects/${id}`);
export const deleteProject = (id: string) =>
  fetchAPI<any>(`/projects/${id}`, { method: "DELETE" });

// Papers
export const getProjectPapers = (projectId: string) =>
  fetchAPI<any[]>(`/papers/by-project/${projectId}`);

export async function uploadPaper(projectId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/papers/upload/${projectId}`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const error = await res.text().catch(() => res.statusText);
    throw new Error(`Upload failed: ${error}`);
  }
  return res.json();
}

export const getPaper = (id: string) => fetchAPI<any>(`/papers/${id}`);

// Assessment
export const getAssessment = (paperId: string) =>
  fetchAPI<any>(`/assessments/by-paper/${paperId}`);

export const getAssessmentSummary = (paperId: string) =>
  fetchAPI<any>(`/assessments/by-paper/${paperId}/summary`);

export const updateRating = (ratingId: string, data: any) =>
  fetchAPI<any>(`/assessments/rating/${ratingId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

// Analysis
export const triggerAnalysis = (paperId: string) =>
  fetchAPI<any>(`/analysis/paper/${paperId}/analyze`, { method: "POST" });

export const getAnalysisStatus = (paperId: string) =>
  fetchAPI<any>(`/analysis/paper/${paperId}/status`);

// Paper sections and chunks
export const getPaperSections = (paperId: string) =>
  fetchAPI<any[]>(`/papers/${paperId}/sections`);

export const getPaperChunks = (paperId: string, page?: number) =>
  fetchAPI<any[]>(`/papers/${paperId}/chunks${page != null ? `?page=${page}` : ""}`);

// COSMIN Checklist
export const getCosminBoxes = () => fetchAPI<any[]>("/cosmin/boxes");

// Assistant
export const sendAssistantMessage = (
  paperId: string,
  messages: { role: string; content: string }[]
) =>
  fetchAPI<{ message: string; tool_calls_made: string[] }>("/assistant/chat", {
    method: "POST",
    body: JSON.stringify({ paper_id: paperId, messages }),
  });

// Export
export function getExportUrl(paperId: string, format: "xlsx" | "csv" = "xlsx") {
  const token = getToken();
  const params = new URLSearchParams({ format });
  if (token) params.set("token", token);
  return `${API_BASE}/export/paper/${paperId}?${params}`;
}
