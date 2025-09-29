

import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <details style={{ whiteSpace: "pre-wrap" }}>
            <summary>Error details</summary>
            {this.state.error?.toString()}
          </details>
          <button
            onClick={() => this.setState({ hasError: false, error: undefined })}
            className="retry-button"
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

// Specialized error boundary for graph visualization
export function GraphErrorFallback({ error, onRetry }: { error?: Error; onRetry: () => void }) {
  return (
    <div className="graph-error-fallback">
      <div className="error-content">
        <h3>Graph visualization failed</h3>
        <p>There was an error rendering the graph. This might be due to:</p>
        <ul>
          <li>Invalid graph data format</li>
          <li>Browser compatibility issues</li>
          <li>Memory constraints with large graphs</li>
        </ul>
        <button onClick={onRetry} className="primary">
          Reload Graph
        </button>
        {error && (
          <details className="error-details">
            <summary>Technical details</summary>
            <pre>{error.toString()}</pre>
          </details>
        )}
      </div>
    </div>
  );
}

// Hook for functional components error handling
export function useErrorHandler() {
  const [error, setError] = React.useState<Error | null>(null);

  const resetError = React.useCallback(() => {
    setError(null);
  }, []);

  const handleError = React.useCallback((error: Error) => {
    console.error("Handled error:", error);
    setError(error);
  }, []);

  React.useEffect(() => {
    if (error) {
      throw error;
    }
  }, [error]);

  return { handleError, resetError };
}