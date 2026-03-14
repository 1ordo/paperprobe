"use client";

import { useState } from "react";
import { Shield, LogIn, AlertCircle } from "lucide-react";
import { login } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      // Use full page reload so the middleware picks up the new cookie
      window.location.href = "/";
    } catch (err: any) {
      setError(err?.message || "Invalid email or password");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface-0 flex items-center justify-center p-4">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center mb-4">
            <Shield className="w-6 h-6 text-accent" />
          </div>
          <h1 className="text-xl font-semibold text-text-primary">COSMIN Checker</h1>
          <p className="text-sm text-text-tertiary mt-1">Sign in to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-surface-1 border border-border-subtle rounded-xl p-6 shadow-card space-y-4">
          {error && (
            <div className="flex items-center gap-2 text-sm text-cosmin-inadequate bg-cosmin-inadequate/10 border border-cosmin-inadequate/20 rounded-lg px-3 py-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-xs font-medium text-text-secondary mb-1.5">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              className="w-full px-3 py-2 bg-surface-2 border border-border-subtle rounded-lg text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent transition-colors"
              placeholder="admin@cosmin.local"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-medium text-text-secondary mb-1.5">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 bg-surface-2 border border-border-subtle rounded-lg text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent transition-colors"
              placeholder="Enter password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {loading ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <LogIn className="w-4 h-4" />
            )}
            Sign in
          </button>
        </form>

        <p className="text-center text-[11px] text-text-tertiary mt-6">
          Risk of Bias Assessment Platform
        </p>
      </div>
    </div>
  );
}
