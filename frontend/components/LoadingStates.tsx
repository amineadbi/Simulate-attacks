"use client";

import { memo } from "react";

export interface LoadingSpinnerProps {
  size?: "small" | "medium" | "large";
  className?: string;
}

export const LoadingSpinner = memo(({ size = "medium", className = "" }: LoadingSpinnerProps) => {
  const sizeClasses = {
    small: "w-4 h-4",
    medium: "w-6 h-6",
    large: "w-8 h-8",
  };

  return (
    <div className={`inline-block animate-spin ${sizeClasses[size]} ${className}`}>
      <div className="loading-spinner">
        <svg viewBox="0 0 24 24" fill="none">
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="31.416"
            strokeDashoffset="31.416"
            className="animate-spin-path"
          />
        </svg>
      </div>
    </div>
  );
});

LoadingSpinner.displayName = "LoadingSpinner";

export interface LoadingStateProps {
  isLoading: boolean;
  error?: string | null;
  children: React.ReactNode;
  loadingText?: string;
  retryAction?: () => void;
}

export const LoadingState = memo(({
  isLoading,
  error,
  children,
  loadingText = "Loading...",
  retryAction,
}: LoadingStateProps) => {
  if (error) {
    return (
      <div className="loading-error">
        <div className="error-icon">⚠️</div>
        <p className="error-message">{error}</p>
        {retryAction && (
          <button onClick={retryAction} className="retry-button">
            Try Again
          </button>
        )}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="loading-container">
        <LoadingSpinner size="medium" />
        <span className="loading-text">{loadingText}</span>
      </div>
    );
  }

  return <>{children}</>;
});

LoadingState.displayName = "LoadingState";

export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  className?: string;
  variant?: "text" | "rectangular" | "circular";
}

export const Skeleton = memo(({
  width = "100%",
  height = "1rem",
  className = "",
  variant = "text",
}: SkeletonProps) => {
  const variantClasses = {
    text: "rounded",
    rectangular: "rounded-md",
    circular: "rounded-full",
  };

  return (
    <div
      className={`skeleton animate-pulse bg-gray-200 ${variantClasses[variant]} ${className}`}
      style={{ width, height }}
    />
  );
});

Skeleton.displayName = "Skeleton";

export interface ProgressBarProps {
  progress: number; // 0-100
  label?: string;
  className?: string;
}

export const ProgressBar = memo(({ progress, label, className = "" }: ProgressBarProps) => {
  const clampedProgress = Math.max(0, Math.min(100, progress));

  return (
    <div className={`progress-container ${className}`}>
      {label && <div className="progress-label">{label}</div>}
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
      <div className="progress-text">{Math.round(clampedProgress)}%</div>
    </div>
  );
});

ProgressBar.displayName = "ProgressBar";

export interface ConnectionStatusProps {
  status: "connecting" | "connected" | "disconnected" | "error";
  message?: string;
}

export const ConnectionStatus = memo(({ status, message }: ConnectionStatusProps) => {
  const statusConfig = {
    connecting: {
      icon: <LoadingSpinner size="small" />,
      color: "text-yellow-600",
      bgColor: "bg-yellow-50",
      text: "Connecting...",
    },
    connected: {
      icon: "🟢",
      color: "text-green-600",
      bgColor: "bg-green-50",
      text: "Connected",
    },
    disconnected: {
      icon: "🔴",
      color: "text-gray-600",
      bgColor: "bg-gray-50",
      text: "Disconnected",
    },
    error: {
      icon: "⚠️",
      color: "text-red-600",
      bgColor: "bg-red-50",
      text: "Connection Error",
    },
  };

  const config = statusConfig[status];

  return (
    <div className={`connection-status ${config.bgColor} ${config.color}`}>
      <span className="status-icon">{config.icon}</span>
      <span className="status-text">{message || config.text}</span>
    </div>
  );
});

ConnectionStatus.displayName = "ConnectionStatus";