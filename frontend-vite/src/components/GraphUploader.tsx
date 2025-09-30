import { ChangeEvent, useState, useCallback, DragEvent } from "react";
import { Upload, FileJson, Check, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { loadGraph } from "../lib/api";
import type { GraphPayload } from "../types/graph";

interface GraphUploaderProps {
  onGraphLoaded: (payload: GraphPayload) => void;
}

type UploadStatus = "idle" | "uploading" | "success" | "error";

export default function GraphUploader({ onGraphLoaded }: GraphUploaderProps) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [statusMessage, setStatusMessage] = useState<string>("No graph loaded");
  const [isDragging, setIsDragging] = useState(false);
  const [graphStats, setGraphStats] = useState<{ nodes: number; edges: number } | null>(null);

  async function hydrateBackend(payload: GraphPayload) {
    try {
      await loadGraph(payload);
      setStatus("success");
      setGraphStats({ nodes: payload.nodes.length, edges: payload.edges.length });
      setStatusMessage(
        `Successfully synced graph (${payload.nodes.length} nodes, ${payload.edges.length} edges)`
      );
    } catch (error) {
      console.error("Backend sync error:", error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      setStatus("error");
      setStatusMessage(`Failed to sync backend: ${errorMessage}`);
    }
  }

  async function parseGraph(text: string) {
    try {
      setStatus("uploading");
      setStatusMessage("Parsing graph data...");

      const payload = JSON.parse(text) as GraphPayload;
      if (!payload.nodes || !payload.edges) {
        throw new Error("Missing nodes or edges array in graph data");
      }

      onGraphLoaded(payload);
      setStatusMessage("Graph loaded, syncing to backend...");
      await hydrateBackend(payload);
    } catch (error) {
      console.error(error);
      setStatus("error");
      setStatusMessage(`Failed to parse graph: ${(error as Error).message}`);
    }
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    await parseGraph(text);
  }

  async function loadSampleGraph() {
    try {
      setStatus("uploading");
      setStatusMessage("Loading sample graph...");
      const response = await fetch("/sample-graph.json");
      const text = await response.text();
      await parseGraph(text);
    } catch (error) {
      console.error(error);
      setStatus("error");
      setStatusMessage("Unable to load sample graph");
    }
  }

  // Drag and drop handlers
  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(async (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (!file) return;

    if (!file.name.endsWith(".json")) {
      setStatus("error");
      setStatusMessage("Please upload a JSON file");
      return;
    }

    const text = await file.text();
    await parseGraph(text);
  }, []);

  const getStatusIcon = () => {
    switch (status) {
      case "uploading":
        return <Upload className="h-4 w-4 animate-pulse" />;
      case "success":
        return <Check className="h-4 w-4" />;
      case "error":
        return <AlertCircle className="h-4 w-4" />;
      default:
        return <FileJson className="h-4 w-4" />;
    }
  };

  const getStatusBadge = () => {
    switch (status) {
      case "uploading":
        return <Badge variant="info">Loading...</Badge>;
      case "success":
        return <Badge variant="success">Loaded</Badge>;
      case "error":
        return <Badge variant="destructive">Error</Badge>;
      default:
        return null;
    }
  };

  return (
    <Card className="glass-panel">
      <CardContent className="pt-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <FileJson className="h-4 w-4" />
            Graph Data
          </h3>
          {getStatusBadge()}
        </div>

        {/* Drag and Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={cn(
            "border-2 border-dashed rounded-lg p-6 transition-all duration-200",
            isDragging
              ? "border-primary bg-primary/10 scale-[1.02]"
              : "border-muted hover:border-primary/50 hover:bg-muted/50"
          )}
        >
          <div className="flex flex-col items-center justify-center gap-3 text-center">
            <div
              className={cn(
                "h-12 w-12 rounded-full flex items-center justify-center transition-colors",
                isDragging
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              )}
            >
              <Upload className={cn("h-6 w-6", isDragging && "animate-bounce")} />
            </div>

            <div>
              <p className="text-sm font-medium mb-1">
                {isDragging ? "Drop your file here" : "Drag & drop your graph JSON"}
              </p>
              <p className="text-xs text-muted-foreground">or click the button below to browse</p>
            </div>

            <div className="flex gap-2 w-full mt-2">
              <Button
                type="button"
                variant="outline"
                className="flex-1 relative"
                disabled={status === "uploading"}
              >
                <input
                  type="file"
                  accept="application/json,.json"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  disabled={status === "uploading"}
                />
                <Upload className="h-4 w-4 mr-2" />
                Browse Files
              </Button>

              <Button
                type="button"
                variant="secondary"
                onClick={loadSampleGraph}
                disabled={status === "uploading"}
                className="flex-1"
              >
                <FileJson className="h-4 w-4 mr-2" />
                Load Sample
              </Button>
            </div>
          </div>
        </div>

        {/* Status Message */}
        <div
          className={cn(
            "flex items-start gap-2 p-3 rounded-md text-sm transition-colors",
            status === "success" && "bg-green-500/10 border border-green-500/20",
            status === "error" && "bg-red-500/10 border border-red-500/20",
            status === "uploading" && "bg-blue-500/10 border border-blue-500/20",
            status === "idle" && "bg-muted/50 border border-muted"
          )}
        >
          <div className="mt-0.5">{getStatusIcon()}</div>
          <div className="flex-1">
            <p className="leading-relaxed">{statusMessage}</p>
            {graphStats && status === "success" && (
              <div className="flex gap-3 mt-2">
                <Badge variant="secondary" className="text-xs">
                  {graphStats.nodes} nodes
                </Badge>
                <Badge variant="secondary" className="text-xs">
                  {graphStats.edges} edges
                </Badge>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}