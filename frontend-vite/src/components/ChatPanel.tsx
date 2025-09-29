

import { FormEvent, useEffect, useRef, useState } from "react";
import type { ConnectionState } from "../types/events";

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
}

interface ChatPanelProps {
  messages: ChatMessageItem[];
  connectionState: ConnectionState;
  onSend: (text: string) => void;
  disabled?: boolean;
  isWaitingForAgent?: boolean;
}

const PLACEHOLDER = "Ask the agent to explore the graph or plan a scenario...";

export default function ChatPanel({
  messages,
  connectionState,
  onSend,
  disabled = false,
  isWaitingForAgent = false
}: ChatPanelProps) {
  const [draft, setDraft] = useState<string>("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = draft.trim();
    if (!value || disabled || connectionState !== "open") {
      return;
    }
    onSend(value);
    setDraft("");
  }

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <div>
          <h2>Agent Chat</h2>
          <p>Talk to the LangGraph assistant about this environment.</p>
        </div>
        <span className={`connection connection-${connectionState}`}>
          {connectionState === "open"
            ? "Live"
            : connectionState === "connecting"
            ? "Connecting"
            : connectionState === "retrying"
            ? "Retrying"
            : connectionState === "error"
            ? "Error"
            : "Offline"}
        </span>
      </header>
      <div className="chat-messages">
        {messages.map((message) => (
          <article key={message.id} className={`chat-message role-${message.role}`}>
            <div className="meta">
              <span className="role">{message.role === "assistant" ? "Agent" : "You"}</span>
              <time>{new Date(message.createdAt).toLocaleTimeString()}</time>
            </div>
            <p>{message.content}</p>
          </article>
        ))}
        <div ref={endRef} />
      </div>
      <form className="chat-composer" onSubmit={handleSubmit}>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={PLACEHOLDER}
          rows={3}
          disabled={disabled || connectionState !== "open"}
        />
        <button
          type="submit"
          className="primary"
          disabled={disabled || connectionState !== "open" || !draft.trim()}
        >
          {isWaitingForAgent ? "Waiting..." : "Send"}
        </button>
      </form>
    </section>
  );
}
