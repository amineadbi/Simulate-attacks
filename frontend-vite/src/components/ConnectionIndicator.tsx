import { Wifi, WifiOff, Loader2, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ConnectionState } from "../types/events";

interface ConnectionIndicatorProps {
  state: ConnectionState;
  lastConnectedAt?: string;
}

const CONFIG: Record<ConnectionState, { icon: React.ReactNode; label: string; variant: string }> = {
  idle: {
    icon: <WifiOff className="h-3 w-3" />,
    label: "Idle",
    variant: "secondary",
  },
  connecting: {
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
    label: "Connecting",
    variant: "warning",
  },
  open: {
    icon: <Wifi className="h-3 w-3 pulse" />,
    label: "Connected",
    variant: "success",
  },
  retrying: {
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
    label: "Reconnecting",
    variant: "warning",
  },
  closed: {
    icon: <WifiOff className="h-3 w-3" />,
    label: "Offline",
    variant: "secondary",
  },
  error: {
    icon: <AlertCircle className="h-3 w-3" />,
    label: "Error",
    variant: "destructive",
  },
};

export default function ConnectionIndicator({ state, lastConnectedAt }: ConnectionIndicatorProps) {
  const config = CONFIG[state];

  return (
    <Badge variant={config.variant as any} className="gap-1.5 px-2.5 py-1">
      {config.icon}
      <span className="text-xs font-medium">{config.label}</span>
      {lastConnectedAt && state === "open" && (
        <span className="text-xs opacity-75">
          {new Date(lastConnectedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      )}
    </Badge>
  );
}