

import { FormEvent, useState } from "react";
import { runCypher } from "../lib/api";
import type { CypherResult } from "../types/graph";

interface CypherQueryBarProps {
  defaultQuery?: string;
  onResult?: (result: CypherResult) => void;
}

export default function CypherQueryBar({ defaultQuery, onResult }: CypherQueryBarProps) {
  const [query, setQuery] = useState<string>(
    defaultQuery ?? "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 25"
  );
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CypherResult | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await runCypher(query);
      setResult(response);
      onResult?.(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="cypher-panel">
      <form className="cypher-form" onSubmit={handleSubmit}>
        <label htmlFor="cypher-query">Cypher Query</label>
        <textarea
          id="cypher-query"
          value={query}
          rows={4}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="MATCH (n) RETURN n LIMIT 25"
        />
        <div className="cypher-actions">
          <button type="submit" disabled={loading}>
            {loading ? "Running..." : "Run Query"}
          </button>
        </div>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {result ? (
        <pre className="cypher-result" aria-live="polite">
          {JSON.stringify(result, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
