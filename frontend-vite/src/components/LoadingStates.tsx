import { memo } from "react";
import { Loader2, AlertCircle, CheckCircle2, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface LoadingSpinnerProps {
  size?: "small" | "medium" | "large";
  className?: string;
}

export const LoadingSpinner = memo(({ size = "medium", className = "" }: LoadingSpinnerProps) => {
  const sizeClasses = {
    small: "h-4 w-4",
    medium: "h-6 w-6",
    large: "h-8 w-8",
  };

  return (
    <Loader2 className={cn("animate-spin text-primary", sizeClasses[size], className)} />
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
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <div className="h-12 w-12 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
          <AlertCircle className="h-6 w-6 text-destructive" />
        </div>
        <h3 className="text-sm font-semibold mb-2">Error Loading Content</h3>
        <p className="text-sm text-muted-foreground mb-4 max-w-sm">{error}</p>
        {retryAction && (
          <Button onClick={retryAction} variant="outline" size="sm">
            Try Again
          </Button>
        )}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-8">
        <LoadingSpinner size="large" className="mb-4" />
        <p className="text-sm text-muted-foreground">{loadingText}</p>
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
      className={cn("skeleton bg-muted", variantClasses[variant], className)}
      style={{ width, height }}
    />
  );
});

Skeleton.displayName = "Skeleton";

export interface ProgressBarProps {
  progress: number;
  label?: string;
  className?: string;
}

export const ProgressBar = memo(({ progress, label, className = "" }: ProgressBarProps) => {
  const clampedProgress = Math.max(0, Math.min(100, progress));

  return (
    <div className={cn("space-y-2", className)}>
      {label && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-medium">{Math.round(clampedProgress)}%</span>
        </div>
      )}
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div
          className="h-full bg-primary transition-all duration-300 ease-out"
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
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
      icon: <Loader2 className="h-3 w-3 animate-spin" />,
      variant: "warning" as const,
      text: "Connecting...",
    },
    connected: {
      icon: <CheckCircle2 className="h-3 w-3" />,
      variant: "success" as const,
      text: "Connected",
    },
    disconnected: {
      icon: <WifiOff className="h-3 w-3" />,
      variant: "secondary" as const,
      text: "Disconnected",
    },
    error: {
      icon: <AlertCircle className="h-3 w-3" />,
      variant: "destructive" as const,
      text: "Connection Error",
    },
  };

  const config = statusConfig[status];

  return (
    <Badge variant={config.variant} className="gap-1.5 px-2.5 py-1">
      {config.icon}
      <span className="text-xs font-medium">{message || config.text}</span>
    </Badge>
  );
});

ConnectionStatus.displayName = "ConnectionStatus";