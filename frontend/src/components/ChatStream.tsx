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
    <div className="flex h-full flex-col border-r border-slate-800 bg-slate-900">
      <div className="border-b border-slate-800 bg-slate-900/50 px-6 py-4 backdrop-blur">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-mono text-xs font-bold tracking-wider text-slate-400 uppercase">
              AI Copilot Agent
            </h2>
            <p className="mt-0.5 text-[11px] text-slate-500">
              Automated Rule Extraction System
            </p>
          </div>
          <button
            onClick={onNewSession}
            className="rounded-md bg-slate-800 px-2.5 py-1 font-mono text-[10px] text-slate-300 transition hover:bg-slate-700"
          >
            + New Session
          </button>
        </div>

        {sessions.length > 0 && (
          <div className="mt-3">
            <select
              value={sessionId}
              onChange={(e) => onSelectSession(e.target.value)}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-[10px] text-slate-300 focus:border-slate-600 focus:outline-none"
            >
              {sessions
                .filter((s) => s.id.startsWith("sess_"))
                .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.id} · {formatSessionTime(s.updated_at)}
                  </option>
                ))}
            </select>
          </div>
        )}
      </div>

      {/* Messages Stream */}
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex max-w-[90%] flex-col ${
              msg.sender === "user"
                ? "ml-auto items-end"
                : "mr-auto items-start"
            }`}
          >
            <div
              className={`rounded-xl px-4 py-2.5 text-xs leading-relaxed ${
                msg.sender === "user"
                  ? "rounded-br-none bg-blue-600 text-white"
                  : "rounded-bl-none border border-slate-800 bg-slate-950 text-slate-200"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>
            </div>

            {msg.confidence !== undefined && (
              <div className="mt-1.5 px-1 font-mono text-[10px] text-slate-500 italic">
                Confidence: {(msg.confidence * 100).toFixed(0)}%
                {msg.confidence < 0.5 && " — low confidence, review carefully"}
              </div>
            )}

            {msg.payload && (
              <div className="mt-1.5 px-1 font-mono text-[10px] text-slate-500 italic">
                ⚡ Workspace synced instantly with matching rule properties.
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex w-24 items-center space-x-1.5 rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
            <span
              className="h-1 w-1 animate-bounce rounded-full bg-blue-500"
              style={{ animationDelay: "0ms" }}
            />
            <span
              className="h-1 w-1 animate-bounce rounded-full bg-blue-500"
              style={{ animationDelay: "150ms" }}
            />
            <span
              className="h-1 w-1 animate-bounce rounded-full bg-blue-500"
              style={{ animationDelay: "300ms" }}
            />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-slate-800 bg-slate-950 p-4"
      >
        <div className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type an evaluation hypothesis or pattern search..."
            disabled={isLoading}
            className="w-full rounded-xl border border-slate-800 bg-slate-900 py-3 pr-10 pl-4 text-xs text-slate-200 placeholder-slate-500 transition focus:border-slate-700 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 rounded-lg bg-slate-800 p-1.5 text-slate-300 transition hover:bg-slate-700 disabled:opacity-30"
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
