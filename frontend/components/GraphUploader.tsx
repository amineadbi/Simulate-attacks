"use client";

import { ChangeEvent, useState } from "react";
import { loadGraph } from "../lib/api";
import type { GraphPayload } from "../types/graph";

interface GraphUploaderProps {
  onGraphLoaded: (payload: GraphPayload) => void;
}

export default function GraphUploader({ onGraphLoaded }: GraphUploaderProps) {
  const [status, setStatus] = useState<string>("No graph loaded");

  async function hydrateBackend(payload: GraphPayload) {
    try {
      await loadGraph(payload);
      setStatus(
        `Synced graph to backend (nodes: ${payload.nodes.length}, edges: ${payload.edges.length})`
      );
    } catch (error) {
      console.error("Backend sync error:", error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      setStatus(`Failed to sync backend: ${errorMessage}`);
    }
  }

  async function parseGraph(text: string) {
    try {
      const payload = JSON.parse(text) as GraphPayload;
      if (!payload.nodes || !payload.edges) {
        throw new Error("Missing nodes or edges array");
      }
      onGraphLoaded(payload);
      setStatus(`Loaded graph (nodes: ${payload.nodes.length}, edges: ${payload.edges.length})`);
      await hydrateBackend(payload);
    } catch (error) {
      console.error(error);
      setStatus(`Failed to parse graph: ${(error as Error).message}`);
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
      const response = await fetch("/sample-graph.json");
      const text = await response.text();
      await parseGraph(text);
    } catch (error) {
      console.error(error);
      setStatus("Unable to load sample graph");
    }
  }

  return (
    <div className="uploader">
      <div className="uploader-controls">
        <label className="upload-button">
          <input type="file" accept="application/json" onChange={handleFileChange} hidden />
          Upload Graph JSON
        </label>
        <button type="button" onClick={loadSampleGraph} className="secondary">
          Load Sample Graph
        </button>
      </div>
      <p className="uploader-status">{status}</p>
    </div>
  );
}
