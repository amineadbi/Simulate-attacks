// Error recovery and edge case handling utilities

export class AppError extends Error {
  constructor(
    message: string,
    public code: string,
    public recoverable: boolean = true,
    public context?: any
  ) {
    super(message);
    this.name = "AppError";
  }
}

export const ERROR_CODES = {
  WEBSOCKET_CONNECTION_FAILED: "WEBSOCKET_CONNECTION_FAILED",
  GRAPH_RENDER_FAILED: "GRAPH_RENDER_FAILED",
  INVALID_GRAPH_DATA: "INVALID_GRAPH_DATA",
  CHAT_MESSAGE_FAILED: "CHAT_MESSAGE_FAILED",
  SCENARIO_FAILED: "SCENARIO_FAILED",
  MEMORY_LIMIT_EXCEEDED: "MEMORY_LIMIT_EXCEEDED",
} as const;

// Retry mechanism with exponential backoff
export function createRetryHandler<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
) {
  return async (): Promise<T> => {
    let lastError: Error;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error as Error;

        if (attempt === maxRetries) {
          throw new AppError(
            `Operation failed after ${maxRetries} retries: ${lastError.message}`,
            "MAX_RETRIES_EXCEEDED",
            false,
            { originalError: lastError, attempts: attempt + 1 }
          );
        }

        // Exponential backoff with jitter
        const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }

    throw lastError!;
  };
}

// Graph data validation
export function validateGraphData(data: any): boolean {
  try {
    if (!data || typeof data !== "object") return false;
    if (!Array.isArray(data.nodes)) return false;
    if (!Array.isArray(data.edges)) return false;

    // Check nodes have required fields
    for (const node of data.nodes) {
      if (!node.id || typeof node.id !== "string") return false;
      if (!Array.isArray(node.labels)) return false;
    }

    // Check edges have required fields
    for (const edge of data.edges) {
      if (!edge.id || typeof edge.id !== "string") return false;
      if (!edge.source || typeof edge.source !== "string") return false;
      if (!edge.target || typeof edge.target !== "string") return false;
      if (!edge.type || typeof edge.type !== "string") return false;
    }

    return true;
  } catch {
    return false;
  }
}

// Memory monitoring and cleanup
export function checkMemoryUsage(): { used: number; isHigh: boolean } {
  if ('memory' in performance) {
    const memory = (performance as any).memory;
    const usedMB = memory.usedJSHeapSize / 1024 / 1024;
    const limitMB = memory.jsHeapSizeLimit / 1024 / 1024;

    return {
      used: usedMB,
      isHigh: usedMB > limitMB * 0.8, // Consider high if over 80% of limit
    };
  }

  return { used: 0, isHigh: false };
}

// Safe JSON parsing with fallback
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json);
  } catch {
    return fallback;
  }
}

// WebSocket message validation
export function validateWebSocketMessage(message: any): boolean {
  try {
    return (
      message &&
      typeof message === "object" &&
      typeof message.id === "string" &&
      typeof message.type === "string" &&
      typeof message.createdAt === "string"
    );
  } catch {
    return false;
  }
}

// Graph size limits for performance
export const GRAPH_LIMITS = {
  MAX_NODES: 10000,
  MAX_EDGES: 50000,
  WARN_NODES: 1000,
  WARN_EDGES: 5000,
} as const;

export function checkGraphLimits(data: any): {
  valid: boolean;
  warnings: string[];
  errors: string[]
} {
  const warnings: string[] = [];
  const errors: string[] = [];

  if (!validateGraphData(data)) {
    errors.push("Invalid graph data format");
    return { valid: false, warnings, errors };
  }

  const nodeCount = data.nodes.length;
  const edgeCount = data.edges.length;

  if (nodeCount > GRAPH_LIMITS.MAX_NODES) {
    errors.push(`Too many nodes: ${nodeCount} (max: ${GRAPH_LIMITS.MAX_NODES})`);
  } else if (nodeCount > GRAPH_LIMITS.WARN_NODES) {
    warnings.push(`Large graph: ${nodeCount} nodes may impact performance`);
  }

  if (edgeCount > GRAPH_LIMITS.MAX_EDGES) {
    errors.push(`Too many edges: ${edgeCount} (max: ${GRAPH_LIMITS.MAX_EDGES})`);
  } else if (edgeCount > GRAPH_LIMITS.WARN_EDGES) {
    warnings.push(`Large graph: ${edgeCount} edges may impact performance`);
  }

  return {
    valid: errors.length === 0,
    warnings,
    errors,
  };
}

// Circuit breaker pattern for failing operations
export class CircuitBreaker {
  private failures = 0;
  private lastFailureTime = 0;
  private state: "CLOSED" | "OPEN" | "HALF_OPEN" = "CLOSED";

  constructor(
    private threshold: number = 5,
    private timeout: number = 60000 // 1 minute
  ) {}

  async execute<T>(operation: () => Promise<T>): Promise<T> {
    if (this.state === "OPEN") {
      if (Date.now() - this.lastFailureTime < this.timeout) {
        throw new AppError(
          "Circuit breaker is OPEN",
          "CIRCUIT_BREAKER_OPEN",
          true
        );
      } else {
        this.state = "HALF_OPEN";
      }
    }

    try {
      const result = await operation();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess() {
    this.failures = 0;
    this.state = "CLOSED";
  }

  private onFailure() {
    this.failures++;
    this.lastFailureTime = Date.now();

    if (this.failures >= this.threshold) {
      this.state = "OPEN";
    }
  }

  getState() {
    return {
      state: this.state,
      failures: this.failures,
      lastFailureTime: this.lastFailureTime,
    };
  }
}