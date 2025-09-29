import React, { useState } from 'react';
import SimulationMonitor from './SimulationMonitor';

interface SimulationResults {
  job_id: string;
  progress: number;
  status: string;
  steps_completed: number;
  steps_failed: number;
  findings?: any;
}

interface SimulationPanelProps {
  isVisible: boolean;
  onClose: () => void;
}

const SimulationPanel: React.FC<SimulationPanelProps> = ({ isVisible, onClose }) => {
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [completedSimulations, setCompletedSimulations] = useState<SimulationResults[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleSimulationComplete = (results: SimulationResults) => {
    setCompletedSimulations(prev => [results, ...prev].slice(0, 10)); // Keep last 10
    setActiveJobId(null);
  };

  const handleSimulationError = (errorMessage: string) => {
    setError(errorMessage);
    setActiveJobId(null);
  };

  const clearError = () => setError(null);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'failed': return 'text-red-600';
      case 'running': return 'text-blue-600';
      case 'cancelled': return 'text-gray-600';
      default: return 'text-gray-500';
    }
  };

  const formatDuration = (startTime: string, endTime: string) => {
    const start = new Date(startTime);
    const end = new Date(endTime);
    const duration = Math.abs(end.getTime() - start.getTime()) / 1000;

    if (duration < 60) {
      return `${Math.round(duration)}s`;
    } else if (duration < 3600) {
      return `${Math.round(duration / 60)}m`;
    } else {
      return `${Math.round(duration / 3600)}h`;
    }
  };

  if (!isVisible) return null;

  return (
    <>
      {/* Simulation Panel */}
      <div className="fixed top-0 right-0 w-96 h-full bg-white border-l border-gray-200 shadow-lg z-40 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-800">
            🎯 Simulation Center
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl"
          >
            ✕
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="p-4 bg-red-50 border-b border-red-200">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="text-sm font-medium text-red-800">Simulation Error</h4>
                <p className="text-sm text-red-600 mt-1">{error}</p>
              </div>
              <button
                onClick={clearError}
                className="text-red-400 hover:text-red-600"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Active Simulation Info */}
          {activeJobId && (
            <div className="p-4 bg-blue-50 border-b border-blue-200">
              <h3 className="text-sm font-medium text-blue-800 mb-2">Active Simulation</h3>
              <div className="text-sm text-blue-600">
                Job ID: <code className="bg-blue-100 px-1 rounded">{activeJobId}</code>
              </div>
              <div className="text-xs text-blue-500 mt-1">
                Monitor progress in the bottom-right corner
              </div>
            </div>
          )}

          {/* Recent Simulations */}
          <div className="p-4">
            <h3 className="text-sm font-medium text-gray-800 mb-3">Recent Simulations</h3>

            {completedSimulations.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <div className="text-4xl mb-2">🎭</div>
                <p className="text-sm">No simulations yet</p>
                <p className="text-xs mt-1">
                  Ask the agent to run a simulation to see it here
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {completedSimulations.map((sim, index) => (
                  <div key={sim.job_id} className="border border-gray-200 rounded-lg p-3 bg-gray-50">
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-sm font-medium text-gray-800">
                        Simulation #{completedSimulations.length - index}
                      </div>
                      <div className={`text-xs font-medium ${getStatusColor(sim.status)} capitalize`}>
                        {sim.status}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
                      <div>
                        <span className="font-medium">Completed:</span> {sim.steps_completed}
                      </div>
                      <div>
                        <span className="font-medium">Failed:</span> {sim.steps_failed}
                      </div>
                      <div>
                        <span className="font-medium">Success Rate:</span>{' '}
                        {Math.round((sim.steps_completed / (sim.steps_completed + sim.steps_failed)) * 100)}%
                      </div>
                      <div>
                        <span className="font-medium">Progress:</span> {Math.round(sim.progress)}%
                      </div>
                    </div>

                    {sim.findings && (
                      <div className="mt-2 pt-2 border-t border-gray-300">
                        <div className="text-xs text-gray-600">
                          <span className="font-medium">Key Findings:</span>
                          <div className="mt-1 space-y-1">
                            {sim.findings.recommendations?.slice(0, 2).map((rec: string, i: number) => (
                              <div key={i} className="text-xs text-gray-500">
                                • {rec}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="mt-2 text-xs text-gray-400">
                      Job ID: <code className="bg-gray-200 px-1 rounded">{sim.job_id}</code>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Help Section */}
          <div className="p-4 border-t border-gray-200 bg-gray-50">
            <h4 className="text-sm font-medium text-gray-800 mb-2">💡 Quick Commands</h4>
            <div className="space-y-1 text-xs text-gray-600">
              <div>• "Run a lateral movement simulation"</div>
              <div>• "Execute privilege escalation test"</div>
              <div>• "Simulate data exfiltration"</div>
              <div>• "Test persistence mechanisms"</div>
            </div>
          </div>
        </div>
      </div>

      {/* Simulation Monitor (floating) */}
      <SimulationMonitor
        jobId={activeJobId || undefined}
        onComplete={handleSimulationComplete}
        onError={handleSimulationError}
      />
    </>
  );
};

export default SimulationPanel;