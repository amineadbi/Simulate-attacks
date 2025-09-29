import React, { useState, useEffect } from 'react';
import { useAgentEventStream } from '../lib/streaming';

interface SimulationEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  description: string;
  severity: string;
  metadata: Record<string, any>;
}

interface SimulationProgress {
  job_id: string;
  progress: number;
  status: string;
  current_step: number;
  total_steps: number;
  steps_completed: number;
  steps_failed: number;
  event?: SimulationEvent;
}

interface SimulationMonitorProps {
  jobId?: string;
  onComplete?: (results: any) => void;
  onError?: (error: string) => void;
}

const SimulationMonitor: React.FC<SimulationMonitorProps> = ({
  jobId,
  onComplete,
  onError
}) => {
  const [activeSimulation, setActiveSimulation] = useState<SimulationProgress | null>(null);
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [isVisible, setIsVisible] = useState(false);
  const [lastEvent, setLastEvent] = useState<any>(null);

  const { status, metrics, sendMessage } = useAgentEventStream({
    onEvent: (event) => {
      setLastEvent(event);
    },
    onStatusChange: (status) => {
      // Handle status changes if needed
    }
  });

  const isConnected = status === 'open';

  useEffect(() => {
    if (!lastEvent) return;

    const { type, payload } = lastEvent;

    // Handle simulation events
    if (type === 'simulation_event' || type === 'simulation_progress') {
      const simData = payload as SimulationProgress;

      // Only show if we're monitoring this specific job or any job
      if (!jobId || simData.job_id === jobId) {
        setActiveSimulation(simData);
        setIsVisible(true);

        // Add event to history if it contains event data
        if (simData.event) {
          setEvents(prev => [simData.event!, ...prev].slice(0, 20)); // Keep last 20 events
        }

        // Handle completion
        if (simData.status === 'completed') {
          onComplete?.(simData);
          setTimeout(() => setIsVisible(false), 5000); // Auto-hide after 5 seconds
        }

        // Handle errors
        if (simData.status === 'failed') {
          onError?.(simData.event?.description || 'Simulation failed');
        }
      }
    }
  }, [lastEvent, jobId, onComplete, onError]);

  if (!isVisible || !activeSimulation) {
    return null;
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return '⏳';
      case 'initializing': return '🔄';
      case 'running': return '▶️';
      case 'completed': return '✅';
      case 'failed': return '❌';
      case 'cancelled': return '⏹️';
      default: return '📊';
    }
  };

  const getProgressColor = (progress: number) => {
    if (progress < 30) return 'bg-red-500';
    if (progress < 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'text-red-600';
      case 'error': return 'text-red-500';
      case 'warning': return 'text-yellow-500';
      case 'info': return 'text-blue-500';
      default: return 'text-gray-600';
    }
  };

  return (
    <div className="fixed bottom-4 right-4 w-96 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <span className="text-xl">{getStatusIcon(activeSimulation.status)}</span>
          <h3 className="font-semibold text-gray-800">
            Simulation Monitor
          </h3>
          {!isConnected && (
            <span className="text-xs text-red-500">Disconnected</span>
          )}
        </div>
        <button
          onClick={() => setIsVisible(false)}
          className="text-gray-400 hover:text-gray-600"
        >
          ✕
        </button>
      </div>

      {/* Progress */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">
            Step {activeSimulation.current_step + 1} of {activeSimulation.total_steps}
          </span>
          <span className="text-sm text-gray-600">
            {Math.round(activeSimulation.progress)}%
          </span>
        </div>

        <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
          <div
            className={`h-2 rounded-full transition-all duration-300 ${getProgressColor(activeSimulation.progress)}`}
            style={{ width: `${activeSimulation.progress}%` }}
          />
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
          <div>
            <span className="text-gray-600">Completed:</span>
            <span className="ml-1 font-medium text-green-600">
              {activeSimulation.steps_completed}
            </span>
          </div>
          <div>
            <span className="text-gray-600">Failed:</span>
            <span className="ml-1 font-medium text-red-600">
              {activeSimulation.steps_failed}
            </span>
          </div>
        </div>

        {/* Current Status */}
        <div className="text-sm">
          <span className="text-gray-600">Status:</span>
          <span className="ml-1 font-medium capitalize">
            {activeSimulation.status}
          </span>
        </div>
      </div>

      {/* Recent Events */}
      {events.length > 0 && (
        <div className="border-t border-gray-200">
          <div className="p-3">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Recent Activity</h4>
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {events.slice(0, 5).map((event) => (
                <div key={event.event_id} className="text-xs">
                  <div className={`font-medium ${getSeverityColor(event.severity)}`}>
                    {event.description}
                  </div>
                  <div className="text-gray-500">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SimulationMonitor;