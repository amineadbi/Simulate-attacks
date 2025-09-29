import { GraphPayload, CypherResult, ScenarioRunRequest, ScenarioRunStatus } from "../types/graph";

const API_BASE_URL = process.env.NEXT_PUBLIC_MCP_BASE_URL ?? "http://localhost:8000";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed (${response.status}): ${body}`);
  }
  return (await response.json()) as T;
}

export async function loadGraph(payload: GraphPayload): Promise<GraphPayload> {
  const url = `${API_BASE_URL}/tools/load_graph`;
  console.log("Loading graph to:", url);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    console.log("Load graph response status:", response.status);
    return handleResponse<GraphPayload>(response);
  } catch (error) {
    console.error("Network error loading graph:", error);
    throw new Error(`Network error: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

export async function runCypher(query: string, mode: "read" | "write" = "read"): Promise<CypherResult> {
  const response = await fetch(`${API_BASE_URL}/tools/run_cypher`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query, mode })
  });
  return handleResponse<CypherResult>(response);
}

export async function startScenario(payload: ScenarioRunRequest): Promise<ScenarioRunStatus> {
  const response = await fetch(`${API_BASE_URL}/tools/start_attack`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<ScenarioRunStatus>(response);
}

export async function checkScenario(jobId: string): Promise<ScenarioRunStatus> {
  const response = await fetch(`${API_BASE_URL}/tools/check_attack`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ job_id: jobId })
  });
  return handleResponse<ScenarioRunStatus>(response);
}

export async function fetchScenarioResults(jobId: string): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}/tools/fetch_results`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ job_id: jobId })
  });
  return handleResponse<unknown>(response);
}
