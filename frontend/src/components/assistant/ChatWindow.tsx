"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
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

function isTableSeparator(line: string) {
  return /^\|[\s\-:|]+\|$/.test(line.trim());
}

function parseTableRow(line: string) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

function renderTable(lines: string[], keyPrefix: string) {
  const headerCells = parseTableRow(lines[0]);
  const bodyLines = lines.slice(2); // skip header + separator
  return (
    <div key={keyPrefix} className="overflow-x-auto my-2">
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr>
            {headerCells.map((cell, ci) => (
              <th
                key={ci}
                className="text-left px-2 py-1.5 border-b border-border font-semibold text-text-primary bg-surface-0/50"
              >
                {renderInline(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyLines.map((row, ri) => {
            const cells = parseTableRow(row);
            return (
              <tr key={ri} className={ri % 2 === 0 ? "" : "bg-surface-0/30"}>
                {cells.map((cell, ci) => (
                  <td key={ci} className="px-2 py-1.5 border-b border-border/50 text-text-secondary">
                    {renderInline(cell)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MarkdownContent({ text }: { text: string }) {
  // Minimal markdown rendering: bold, inline code, code blocks, lists, tables
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
        // Process lines, collecting table blocks
        const lines = part.split("\n");
        const elements: React.ReactNode[] = [];
        let lineIdx = 0;

        while (lineIdx < lines.length) {
          const line = lines[lineIdx];

          // Detect table: current line starts with |, next line is separator
          if (
            line.trim().startsWith("|") &&
            lineIdx + 1 < lines.length &&
            isTableSeparator(lines[lineIdx + 1])
          ) {
            // Collect header + separator + all body rows
            const tableLines: string[] = [line, lines[lineIdx + 1]];
            lineIdx += 2;
            while (lineIdx < lines.length && lines[lineIdx].trim().startsWith("|") && !isTableSeparator(lines[lineIdx])) {
              tableLines.push(lines[lineIdx]);
              lineIdx++;
            }
            elements.push(renderTable(tableLines, `${i}-tbl-${lineIdx}`));
            continue;
          }

          const j = lineIdx;
          lineIdx++;

          // Headings
          if (line.startsWith("### ")) {
            elements.push(<div key={`${i}-${j}`} className="font-semibold text-text-primary mt-2 mb-1">{line.slice(4)}</div>);
          } else if (line.startsWith("## ")) {
            elements.push(<div key={`${i}-${j}`} className="font-semibold text-text-primary mt-2 mb-1">{line.slice(3)}</div>);
          } else if (line.match(/^[-*] /)) {
            elements.push(<div key={`${i}-${j}`} className="pl-3 before:content-['•'] before:mr-1.5 before:text-accent">{renderInline(line.slice(2))}</div>);
          } else if (line.match(/^\d+\. /)) {
            elements.push(<div key={`${i}-${j}`} className="pl-3">{renderInline(line)}</div>);
          } else if (!line.trim()) {
            elements.push(<div key={`${i}-${j}`} className="h-2" />);
          } else {
            elements.push(<div key={`${i}-${j}`}>{renderInline(line)}</div>);
          }
        }
        return <React.Fragment key={i}>{elements}</React.Fragment>;
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
