"use client";

import { memo, useCallback, useRef, useEffect } from "react";
import { useVirtualList, usePerformanceMonitor } from "../lib/performance";
import type { LogEntry } from "../types/app-state";

interface LogPanelProps {
  logEntries: LogEntry[];
  maxHeight?: number;
}

const LogEntryItem = memo(({ entry, style }: { entry: LogEntry; style: React.CSSProperties }) => (
  <li
    className={`log-entry level-${entry.level ?? "info"}`}
    style={style}
  >
    <span className="timestamp">
      {new Date(entry.createdAt).toLocaleTimeString()}
    </span>
    <span className="message">{entry.message}</span>
  </li>
));

LogEntryItem.displayName = "LogEntryItem";

function OptimizedLogPanel({ logEntries, maxHeight = 400 }: LogPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { start, end } = usePerformanceMonitor("LogPanel render");

  const {
    visibleItems,
    totalHeight,
    updateScrollTop,
  } = useVirtualList({
    items: logEntries,
    itemHeight: 32, // Approximate height of each log entry
    containerHeight: maxHeight,
    overscan: 10,
  });

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    updateScrollTop(e.currentTarget.scrollTop);
  }, [updateScrollTop]);

  useEffect(() => {
    start();
    return () => {
      end();
    };
  }, [logEntries.length]);

  // Auto-scroll to bottom for new entries
  useEffect(() => {
    if (containerRef.current && logEntries.length > 0) {
      const container = containerRef.current;
      const isScrolledToBottom =
        container.scrollHeight - container.scrollTop <= container.clientHeight + 50;

      if (isScrolledToBottom) {
        container.scrollTop = container.scrollHeight;
      }
    }
  }, [logEntries.length]);

  if (logEntries.length === 0) {
    return (
      <section className="log-panel">
        <h2>Activity Log</h2>
        <div className="empty-state">
          <p>No activity yet. Connect to start seeing events.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="log-panel">
      <h2>Activity Log ({logEntries.length} entries)</h2>
      <div
        ref={containerRef}
        className="log-container"
        style={{
          height: maxHeight,
          overflow: "auto",
          position: "relative"
        }}
        onScroll={handleScroll}
      >
        <div style={{ height: totalHeight, position: "relative" }}>
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {visibleItems.map(({ item, index, offsetTop }) => (
              <LogEntryItem
                key={item.id}
                entry={item}
                style={{
                  position: "absolute",
                  top: offsetTop,
                  left: 0,
                  right: 0,
                  height: 32,
                }}
              />
            ))}
          </ul>
        </div>
      </div>
      <div className="log-stats">
        <small>Showing {visibleItems.length} of {logEntries.length} entries</small>
      </div>
    </section>
  );
}

export default memo(OptimizedLogPanel);