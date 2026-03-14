"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { sendAssistantMessage } from "@/lib/api";
import {
  MessageSquare, X, Send, Loader2, RotateCcw, Wrench,
  ChevronDown, Sparkles,
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  toolCalls?: string[];
}

interface ChatWindowProps {
  paperId: string;
  paperTitle: string;
}

function storageKey(paperId: string) {
  return `assistant_chat_${paperId}`;
}

function MarkdownContent({ text }: { text: string }) {
  // Minimal markdown rendering: bold, inline code, code blocks, lists
  const parts = text.split(/(```[\s\S]*?```)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("```")) {
          const code = part.replace(/^```\w*\n?/, "").replace(/```$/, "");
          return (
            <pre key={i} className="bg-surface-0 rounded p-2 my-1 text-[11px] overflow-x-auto font-mono">
              {code}
            </pre>
          );
        }
        // Process inline formatting
        const lines = part.split("\n");
        return lines.map((line, j) => {
          // Headings
          if (line.startsWith("### "))
            return <div key={`${i}-${j}`} className="font-semibold text-text-primary mt-2 mb-1">{line.slice(4)}</div>;
          if (line.startsWith("## "))
            return <div key={`${i}-${j}`} className="font-semibold text-text-primary mt-2 mb-1">{line.slice(3)}</div>;
          // List items
          if (line.match(/^[-*] /))
            return <div key={`${i}-${j}`} className="pl-3 before:content-['•'] before:mr-1.5 before:text-accent">{renderInline(line.slice(2))}</div>;
          // Numbered lists
          if (line.match(/^\d+\. /))
            return <div key={`${i}-${j}`} className="pl-3">{renderInline(line)}</div>;
          // Empty lines
          if (!line.trim()) return <div key={`${i}-${j}`} className="h-2" />;
          // Regular text
          return <div key={`${i}-${j}`}>{renderInline(line)}</div>;
        });
      })}
    </>
  );
}

function renderInline(text: string) {
  // Bold and inline code
  const parts = text.split(/(\*\*.*?\*\*|`[^`]+`)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**"))
      return <strong key={i} className="text-text-primary font-semibold">{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`"))
      return <code key={i} className="bg-surface-0 px-1 rounded text-accent text-[11px] font-mono">{p.slice(1, -1)}</code>;
    return <span key={i}>{p}</span>;
  });
}

export function ChatWindow({ paperId, paperTitle }: ChatWindowProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load chat history from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey(paperId));
      if (saved) setMessages(JSON.parse(saved));
    } catch {}
  }, [paperId]);

  // Save chat history
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem(storageKey(paperId), JSON.stringify(messages));
    }
  }, [messages, paperId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Focus input when opened
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const handleReset = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(storageKey(paperId));
  }, [paperId]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      // Send full history to backend
      const history = newMessages.map((m) => ({ role: m.role, content: m.content }));
      const res = await sendAssistantMessage(paperId, history);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.message,
          toolCalls: res.tool_calls_made,
        },
      ]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${e.message || "Failed to get response"}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <>
      {/* Toggle button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-accent hover:bg-accent-hover text-white shadow-glow flex items-center justify-center transition-all hover:scale-105"
          title="AI Assistant"
        >
          <MessageSquare className="w-5 h-5" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-[420px] h-[600px] max-h-[80vh] bg-surface-1 border border-border rounded-xl shadow-2xl flex flex-col overflow-hidden animate-slide-up">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-surface-2 border-b border-border shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              <Sparkles className="w-4 h-4 text-accent shrink-0" />
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-text-primary truncate">AI Assistant</h3>
                <p className="text-[10px] text-text-tertiary truncate">{paperTitle}</p>
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={handleReset}
                className="p-1.5 rounded-md hover:bg-surface-3 text-text-tertiary hover:text-cosmin-doubtful transition-colors"
                title="Reset conversation"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-md hover:bg-surface-3 text-text-tertiary hover:text-text-primary transition-colors"
                title="Close"
              >
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-auto px-4 py-3 space-y-3">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Sparkles className="w-8 h-8 text-accent/30 mb-3" />
                <p className="text-sm text-text-secondary mb-1">Ask me anything about this paper</p>
                <p className="text-[11px] text-text-tertiary max-w-[280px]">
                  I can look up ratings, evidence, search the text, and explain COSMIN methodology.
                </p>
                <div className="flex flex-wrap gap-1.5 mt-4 justify-center">
                  {[
                    "Summarize the key findings",
                    "Why was Box 9 rated this way?",
                    "What sample size was used?",
                    "Explain the worst score",
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => {
                        setInput(q);
                        inputRef.current?.focus();
                      }}
                      className="text-[11px] px-2.5 py-1.5 rounded-lg bg-surface-3 text-text-secondary hover:text-text-primary hover:bg-surface-4 transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
                    msg.role === "user"
                      ? "bg-accent text-white rounded-br-sm"
                      : "bg-surface-2 text-text-secondary border border-border rounded-bl-sm"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <MarkdownContent text={msg.content} />
                  ) : (
                    msg.content
                  )}
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="flex items-center gap-1 mt-2 pt-2 border-t border-border/50">
                      <Wrench className="w-3 h-3 text-text-tertiary" />
                      <span className="text-[10px] text-text-tertiary font-mono">
                        {msg.toolCalls.join(", ")}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-surface-2 border border-border rounded-xl rounded-bl-sm px-4 py-3 flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />
                  <span className="text-[11px] text-text-tertiary">Thinking...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="px-3 py-3 border-t border-border bg-surface-2 shrink-0">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about this paper..."
                rows={1}
                className="flex-1 resize-none bg-surface-1 border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent transition-colors max-h-24 overflow-auto"
                style={{ minHeight: "36px" }}
                disabled={loading}
              />
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="p-2 rounded-lg bg-accent hover:bg-accent-hover disabled:opacity-30 text-white transition-colors shrink-0"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
