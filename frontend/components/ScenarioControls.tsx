"use client";

import { FormEvent, useMemo, useState } from "react";
import { startScenario } from "../lib/api";
import type { ScenarioRunRequest, ScenarioRunStatus } from "../types/graph";
import type { ConnectionState, OutgoingAgentMessage } from "../types/events";

interface ScenarioControlsProps {
  connectionStatus: ConnectionState;
  latestStatus?: ScenarioRunStatus | null;
  onScenarioStarted?: (status: ScenarioRunStatus) => void;
  onScenarioError?: (message: string) => void;
  sendMessage?: (message: OutgoingAgentMessage) => void;
}

const STATUS_LABELS: Record<ConnectionState, string> = {
  idle: "Idle",
  connecting: "Connecting",
  open: "Live",
  retrying: "Reconnecting",
  closed: "Closed",
  error: "Error"
};

export default function ScenarioControls({
  connectionStatus,
  latestStatus,
  onScenarioStarted,
  onScenarioError,
  sendMessage
}: ScenarioControlsProps) {
  const [platform, setPlatform] = useState<string>("caldera");
  const [scenarioId, setScenarioId] = useState<string>("");
  const [targetSelector, setTargetSelector] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const connectionLabel = useMemo(
    () => STATUS_LABELS[connectionStatus] ?? connectionStatus,
    [connectionStatus]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    try {
      const payload: ScenarioRunRequest = {
        platform,
        scenarioId,
        targetSelector,
        params: {}
      };

      const response = await startScenario(payload);
      onScenarioStarted?.(response);

      if (sendMessage) {
        sendMessage({
          type: "scenario.run",
          scenarioId: response.jobId ?? scenarioId,
          targetSelector,
          platform,
          params: payload.params
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to start scenario";
      onScenarioError?.(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="scenario-panel">
      <div className="scenario-headline">
        <h2>Scenario Runner</h2>
        <span className={`connection connection-${connectionStatus}`}>
          {connectionLabel}
        </span>
      </div>
      <form className="scenario-form" onSubmit={handleSubmit}>
        <label>
          Platform
          <select value={platform} onChange={(event) => setPlatform(event.target.value)}>
            <option value="caldera">Caldera</option>
            <option value="attackiq" disabled>
              AttackIQ (coming soon)
            </option>
            <option value="cymulate" disabled>
              Cymulate (coming soon)
            </option>
            <option value="safebreach" disabled>
              SafeBreach (coming soon)
            </option>
          </select>
        </label>
        <label>
          Scenario ID
          <input
            type="text"
            value={scenarioId}
            onChange={(event) => setScenarioId(event.target.value)}
            placeholder="e.g. 54c3b61e-attack-chain"
            required
          />
        </label>
        <label>
          Target Selector
          <input
            type="text"
            value={targetSelector}
            onChange={(event) => setTargetSelector(event.target.value)}
            placeholder="MATCH (n:Host {role: 'domain-controller'}) RETURN n"
            required
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Starting..." : "Run Scenario"}
        </button>
      </form>
      {latestStatus ? (
        <div className="scenario-status">
          <p>
            <strong>Job:</strong> {latestStatus.jobId}
          </p>
          <p>
            <strong>Status:</strong> {latestStatus.status}
          </p>
          {latestStatus.details ? <p className="description">{latestStatus.details}</p> : null}
        </div>
      ) : (
        <p className="scenario-placeholder">No scenario status received yet.</p>
      )}
    </section>
  );
}
