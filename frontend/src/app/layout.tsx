import type { Metadata } from "next";
import { Shield, FolderOpen, Activity } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: "COSMIN Checker",
  description: "AI-assisted COSMIN Risk of Bias assessment platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-surface-0 text-text-primary">
        <nav className="bg-surface-1 border-b border-border-subtle sticky top-0 z-50">
          <div className="flex items-center justify-between px-6 h-14 max-w-[1600px] mx-auto">
            <a href="/" className="flex items-center gap-3 group">
              <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center group-hover:bg-accent/20 transition-colors">
                <Shield className="w-4 h-4 text-accent" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="font-semibold text-[15px] text-text-primary tracking-tight">
                  COSMIN Checker
                </span>
                <span className="text-[10px] font-mono text-text-tertiary tracking-widest uppercase">
                  v0.1
                </span>
              </div>
            </a>
            <div className="flex items-center gap-1">
              <a
                href="/"
                className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm text-text-secondary hover:text-text-primary hover:bg-surface-3 transition-colors"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                Projects
              </a>
              <div className="flex items-center gap-2 px-3 py-1.5 text-sm text-text-tertiary">
                <Activity className="w-3.5 h-3.5" />
                <span className="text-[11px] font-mono">Risk of Bias</span>
              </div>
            </div>
          </div>
        </nav>
        <main className="relative">{children}</main>
      </body>
    </html>
  );
}
