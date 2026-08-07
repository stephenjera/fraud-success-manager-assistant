import React, { useState, useRef, useEffect } from "react";
import type { Message, SessionItem } from "../types/api";

interface ChatStreamProps {
  sessionId: string;
  messages: Message[];
  isLoading: boolean;
  onSendPrompt: (prompt: string) => void;
  sessions: SessionItem[];
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
}

export const ChatStream: React.FC<ChatStreamProps> = ({
  sessionId,
  messages,
  isLoading,
  onSendPrompt,
  sessions,
  onSelectSession,
  onNewSession,
}) => {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendPrompt(input.trim());
    setInput("");
  };

  const formatSessionTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleTimeString();
    } catch {
      return iso.substring(11, 16);
    }
  };

  return (
    <div className="flex h-full flex-col border-r border-border bg-surface">
      <div className="border-b border-border bg-surface-2/50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-text">Agent Chat</h2>
            <p className="mt-0.5 text-xs text-text-muted">
              Ask about fraud patterns or anomalies
            </p>
          </div>
          <button
            onClick={onNewSession}
            className="rounded-md bg-surface-2 px-2.5 py-1 text-xs text-text transition hover:bg-border"
          >
            New Session
          </button>
        </div>

        {sessions.length > 0 && (
          <div className="mt-3">
            <select
              value={sessionId}
              onChange={(e) => onSelectSession(e.target.value)}
              className="w-full rounded-md border border-border bg-base px-3 py-1.5 text-xs text-text focus:border-border-highlight focus:outline-none"
            >
              {sessions
                .filter((s) => s.id.startsWith("sess_"))
                .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.id} - {formatSessionTime(s.updated_at)}
                  </option>
                ))}
            </select>
          </div>
        )}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className="flex flex-col"
          >
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-medium text-text-dim uppercase">
                {msg.sender === "user" ? "you" : "agent"}
              </span>
              <span className="text-[10px] text-text-dim">
                {msg.timestamp}
              </span>
            </div>
            <div
              className={`mt-1 rounded-lg border-l-2 px-3 py-2 text-sm leading-relaxed ${
                msg.sender === "user"
                  ? "border-l-accent bg-accent-dim/10 text-text"
                  : "border-l-border-highlight bg-base text-text"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>
            </div>

            {msg.confidence !== undefined && (
              <div className="mt-1.5 pl-1">
                <span
                  className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                    msg.confidence >= 0.7
                      ? "text-accent"
                      : msg.confidence >= 0.5
                        ? "text-warning"
                        : "text-critical"
                  }`}
                >
                  {msg.confidence >= 0.7
                    ? "high"
                    : msg.confidence >= 0.5
                      ? "medium"
                      : "low"}{" "}
                  confidence ({(msg.confidence * 100).toFixed(0)}%)
                </span>
              </div>
            )}

            {msg.payload && (
              <div className="mt-1.5 pl-1 text-[10px] text-accent italic">
                Workspace synced with matching rule properties
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 pl-1">
            <div className="h-0.5 w-16 animate-pulse-slow rounded-full bg-accent" />
            <span className="text-xs text-text-muted">Agent is thinking...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-border bg-base p-4"
      >
        <div className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question or describe a pattern..."
            disabled={isLoading}
            className="w-full rounded-xl border border-border bg-surface py-3 pr-10 pl-4 text-sm text-text placeholder-text-dim transition focus:border-border-highlight focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 rounded-lg bg-accent-dim p-1.5 text-accent transition hover:bg-accent hover:text-base disabled:opacity-30"
          >
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.5"
                d="M14 5l7 7m0 0l-7 7m7-7H3"
              />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
};
