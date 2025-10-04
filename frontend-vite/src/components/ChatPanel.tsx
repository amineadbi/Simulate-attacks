import { FormEvent, useEffect, useRef, useState } from "react";
import { Send, Bot, User, Loader2, Workflow } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import AgentStepsPanel from "./AgentStepsPanel";
import type { ConnectionState } from "../types/events";
import type { AgentStep } from "../types/app-state";

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
  agentSteps?: AgentStep[];
}

const PLACEHOLDER = "Ask the agent to explore the graph or plan a scenario...";

export default function ChatPanel({
  messages,
  connectionState,
  onSend,
  disabled = false,
  isWaitingForAgent = false,
  agentSteps = []
}: ChatPanelProps) {
  const [draft, setDraft] = useState<string>("");
  const [showSteps, setShowSteps] = useState<boolean>(false);
  const endRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  // Auto-show steps when agent is processing
  useEffect(() => {
    if (isWaitingForAgent && agentSteps.length > 0) {
      setShowSteps(true);
    }
  }, [isWaitingForAgent, agentSteps.length]);

  const hasActiveSteps = agentSteps.some(step => step.status === "running");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = draft.trim();
    if (!value || disabled || connectionState !== "open") {
      return;
    }
    onSend(value);
    setDraft("");
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (draft.trim() && !disabled && connectionState === "open") {
        onSend(draft.trim());
        setDraft("");
      }
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Agent Steps Toggle */}
      {agentSteps.length > 0 && (
        <div className="px-6 pt-4 pb-2">
          <Button
            onClick={() => setShowSteps(!showSteps)}
            variant="ghost"
            size="sm"
            className="w-full gap-2 text-xs"
          >
            <Workflow className="h-3 w-3" />
            {showSteps ? "Hide" : "Show"} Agent Steps
            {hasActiveSteps && (
              <Badge variant="default" className="ml-auto h-5">
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
                Processing
              </Badge>
            )}
            {!hasActiveSteps && agentSteps.length > 0 && (
              <Badge variant="secondary" className="ml-auto h-5">
                {agentSteps.length}
              </Badge>
            )}
          </Button>
        </div>
      )}

      {/* Agent Steps Panel */}
      {showSteps && agentSteps.length > 0 && (
        <div className="border-b border-white/10">
          <AgentStepsPanel steps={agentSteps} className="max-h-64" />
        </div>
      )}

      {/* Messages */}
      <ScrollArea className="flex-1 px-6 py-4">
        <div className="space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Bot className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Start a conversation</h3>
              <p className="text-sm text-muted-foreground max-w-xs">
                Ask the AI agent about your network graph, plan attack scenarios, or explore vulnerabilities.
              </p>
            </div>
          )}

          {messages.map((message) => {
            const isUser = message.role === "user";
            const isSystem = message.role === "system";

            return (
              <div
                key={message.id}
                className={cn(
                  "flex gap-3 animate-fade-in",
                  isUser ? "flex-row-reverse" : "flex-row"
                )}
              >
                {/* Avatar */}
                <div
                  className={cn(
                    "h-8 w-8 rounded-full flex items-center justify-center shrink-0",
                    isUser
                      ? "bg-gradient-to-br from-green-500 to-emerald-600"
                      : "bg-gradient-to-br from-blue-500 to-purple-600"
                  )}
                >
                  {isUser ? (
                    <User className="h-4 w-4 text-white" />
                  ) : (
                    <Bot className="h-4 w-4 text-white" />
                  )}
                </div>

                {/* Message Bubble */}
                <div className={cn("flex-1 space-y-1", isUser ? "items-end" : "items-start")}>
                  <div className="flex items-baseline gap-2">
                    {!isUser && (
                      <span className="text-xs font-medium text-primary">Agent</span>
                    )}
                    {isUser && (
                      <span className="text-xs font-medium text-green-400">You</span>
                    )}
                    <time className="text-xs text-muted-foreground">
                      {new Date(message.createdAt).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit"
                      })}
                    </time>
                  </div>

                  <div
                    className={cn(
                      "rounded-lg px-4 py-3 max-w-[85%] inline-block",
                      isUser
                        ? "bg-gradient-to-br from-green-500/20 to-emerald-600/20 border border-green-500/30"
                        : isSystem
                        ? "bg-muted/50 border border-muted"
                        : "bg-primary/10 border border-primary/30"
                    )}
                  >
                    {isUser ? (
                      <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
                    ) : (
                      <div className="prose prose-sm prose-invert max-w-none">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            p: ({ children }) => (
                              <p className="text-sm leading-relaxed mb-2 last:mb-0">{children}</p>
                            ),
                            ul: ({ children }) => (
                              <ul className="list-disc list-inside text-sm space-y-1 my-2">{children}</ul>
                            ),
                            ol: ({ children }) => (
                              <ol className="list-decimal list-inside text-sm space-y-1 my-2">{children}</ol>
                            ),
                            code: ({ className, children, ...props }) => {
                              const inline = !className;
                              return inline ? (
                                <code
                                  className="bg-muted/50 px-1.5 py-0.5 rounded text-xs font-mono"
                                  {...props}
                                >
                                  {children}
                                </code>
                              ) : (
                                <code
                                  className="block bg-muted/50 p-3 rounded-md text-xs font-mono overflow-x-auto my-2"
                                  {...props}
                                >
                                  {children}
                                </code>
                              );
                            },
                            strong: ({ children }) => (
                              <strong className="font-semibold text-foreground">{children}</strong>
                            ),
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {isWaitingForAgent && (
            <div className="flex gap-3">
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shrink-0">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <div className="flex-1 space-y-1">
                <span className="text-xs font-medium text-primary">Agent</span>
                <div className="rounded-lg px-4 py-3 bg-primary/10 border border-primary/30 inline-block">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <span className="text-sm text-muted-foreground">Thinking...</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={endRef} />
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="border-t border-white/10 p-4 bg-card/50">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={PLACEHOLDER}
            disabled={disabled || connectionState !== "open"}
            className="min-h-[80px] resize-none bg-background/50 border-white/10 focus:border-primary/50"
          />
          <div className="flex flex-col gap-2">
            <Button
              type="submit"
              disabled={disabled || connectionState !== "open" || !draft.trim() || isWaitingForAgent}
              size="icon"
              className="h-10 w-10 shrink-0"
            >
              {isWaitingForAgent ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>

            {connectionState !== "open" && (
              <Badge variant="warning" className="text-xs whitespace-nowrap">
                {connectionState === "connecting" ? "Connecting..." : "Offline"}
              </Badge>
            )}
          </div>
        </form>
        <p className="text-xs text-muted-foreground mt-2">
          Press <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">Enter</kbd> to send,
          <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs ml-1">Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  );
}