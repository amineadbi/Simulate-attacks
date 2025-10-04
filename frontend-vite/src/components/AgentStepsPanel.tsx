import { CheckCircle2, Circle, Loader2, XCircle, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AgentStep } from "../types/app-state";
import "../styles/agent-steps-animations.css";

interface AgentStepsPanelProps {
  steps: AgentStep[];
  className?: string;
}

const NODE_DISPLAY_NAMES: Record<string, string> = {
  intent_classifier: "Intent Classifier",
  graph_tools: "Graph Tools",
  scenario_planner: "Scenario Planner",
  cypher_runner: "Cypher Runner",
  result_ingest: "Result Ingest",
  respond: "Response Generator",
  router: "Router",
};

function getNodeDisplayName(node: string): string {
  return NODE_DISPLAY_NAMES[node] || node.split("_").map(word =>
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(" ");
}

function formatDuration(ms?: number): string {
  if (!ms) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export default function AgentStepsPanel({ steps, className }: AgentStepsPanelProps) {
  if (steps.length === 0) {
    return (
      <div className={cn("flex items-center justify-center p-6 text-center", className)}>
        <p className="text-sm text-muted-foreground">
          No agent steps to display yet. Steps will appear when the agent is processing your request.
        </p>
      </div>
    );
  }

  return (
    <ScrollArea className={cn("h-full", className)}>
      <div className="space-y-2 p-4">
        {steps.map((step, index) => {
          const isLast = index === steps.length - 1;
          const displayName = getNodeDisplayName(step.node);
          const duration = step.duration ? formatDuration(step.duration) : null;

          return (
            <div
              key={step.id}
              className={cn(
                "relative flex items-start gap-3 p-3 rounded-lg border transition-all agent-step-item",
                step.status === "running" && "border-blue-500/50 bg-blue-500/5 agent-step-running",
                step.status === "completed" && "border-green-500/30 bg-green-500/5 agent-step-complete",
                step.status === "error" && "border-red-500/50 bg-red-500/10 agent-step-error",
                "agent-step-enter"
              )}
            >
              {/* Status Icon */}
              <div className="shrink-0 mt-0.5">
                {step.status === "running" && (
                  <Loader2 className="h-4 w-4 text-blue-400 agent-steps-spinner" />
                )}
                {step.status === "completed" && (
                  <CheckCircle2 className="h-4 w-4 text-green-400 agent-step-complete" />
                )}
                {step.status === "error" && (
                  <XCircle className="h-4 w-4 text-red-400 agent-step-error" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-baseline justify-between gap-2">
                  <h4 className={cn(
                    "text-sm font-medium truncate",
                    step.status === "running" && "text-blue-400",
                    step.status === "completed" && "text-green-400",
                    step.status === "error" && "text-red-400"
                  )}>
                    {displayName}
                  </h4>
                  {duration && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground shrink-0 agent-step-duration">
                      <Clock className="h-3 w-3" />
                      {duration}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <time>
                    {new Date(step.startedAt).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit"
                    })}
                  </time>
                  {step.status === "running" && (
                    <span className="text-blue-400">• Processing...</span>
                  )}
                  {step.status === "completed" && step.completedAt && (
                    <span className="text-green-400">• Completed</span>
                  )}
                  {step.status === "error" && (
                    <span className="text-red-400">• Failed</span>
                  )}
                </div>

                {step.error && (
                  <div className="mt-2 p-2 rounded bg-red-500/10 border border-red-500/20">
                    <p className="text-xs text-red-400">{step.error}</p>
                  </div>
                )}
              </div>

              {/* Connection Line to Next Step */}
              {!isLast && (
                <div className="absolute left-5 top-12 bottom-0 w-px bg-border agent-step-connection-line" />
              )}
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}
