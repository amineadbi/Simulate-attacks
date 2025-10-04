import { AlertTriangle, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PendingConfirmation } from "../types/app-state";

interface ConfirmationDialogProps {
  confirmation: PendingConfirmation;
  onApprove: (confirmationId: string) => void;
  onReject: (confirmationId: string) => void;
}

export default function ConfirmationDialog({
  confirmation,
  onApprove,
  onReject,
}: ConfirmationDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
      <Card className="max-w-md w-full glass-panel border-yellow-500/50">
        <CardHeader>
          <div className="flex items-start gap-3">
            <div className="h-10 w-10 rounded-full bg-yellow-500/20 flex items-center justify-center shrink-0">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
            </div>
            <div className="flex-1">
              <CardTitle className="text-lg">Confirmation Required</CardTitle>
              <Badge variant="secondary" className="mt-1 text-xs">
                {confirmation.action}
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          <p className="text-sm text-foreground">{confirmation.description}</p>

          {confirmation.details && Object.keys(confirmation.details).length > 0 && (
            <div className="rounded-md bg-muted/50 p-3 space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase">Details</p>
              <div className="space-y-1">
                {Object.entries(confirmation.details).map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-2 text-sm">
                    <span className="text-muted-foreground">{key}:</span>
                    <span className="font-mono text-xs">{String(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="p-3 rounded-md bg-yellow-500/10 border border-yellow-500/20">
            <p className="text-xs text-yellow-500">
              This action requires your approval before the agent can proceed. Review the details carefully.
            </p>
          </div>
        </CardContent>

        <CardFooter className="flex gap-3">
          <Button
            onClick={() => onReject(confirmation.id)}
            variant="outline"
            className="flex-1 gap-2"
          >
            <X className="h-4 w-4" />
            Reject
          </Button>
          <Button
            onClick={() => onApprove(confirmation.id)}
            variant="default"
            className="flex-1 gap-2 bg-green-600 hover:bg-green-700"
          >
            <Check className="h-4 w-4" />
            Approve
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
