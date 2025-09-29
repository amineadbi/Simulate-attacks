import { useCallback, useRef, useMemo } from "react";

// Debounce hook for performance optimization
export function useDebounce<T extends (...args: any[]) => any>(
  callback: T,
  delay: number
): T {
  const timeoutRef = useRef<NodeJS.Timeout>();

  return useCallback((...args: Parameters<T>) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      callback(...args);
    }, delay);
  }, [callback, delay]) as T;
}

// Throttle hook for limiting function calls
export function useThrottle<T extends (...args: any[]) => any>(
  callback: T,
  delay: number
): T {
  const lastCallRef = useRef<number>(0);

  return useCallback((...args: Parameters<T>) => {
    const now = Date.now();
    if (now - lastCallRef.current >= delay) {
      lastCallRef.current = now;
      callback(...args);
    }
  }, [callback, delay]) as T;
}

// Memoized computation hook
export function useMemoizedComputation<T, D extends readonly unknown[]>(
  computation: () => T,
  deps: D,
  isEqual?: (a: T, b: T) => boolean
): T {
  const lastResultRef = useRef<T>();
  const lastDepsRef = useRef<D>();

  return useMemo(() => {
    // Check if dependencies changed
    if (lastDepsRef.current &&
        lastDepsRef.current.length === deps.length &&
        lastDepsRef.current.every((dep, index) => dep === deps[index])) {

      // If we have a custom equality check and result hasn't changed
      if (isEqual && lastResultRef.current) {
        const newResult = computation();
        if (isEqual(lastResultRef.current, newResult)) {
          return lastResultRef.current;
        }
        lastResultRef.current = newResult;
        return newResult;
      }

      // Return cached result if deps haven't changed
      if (lastResultRef.current !== undefined) {
        return lastResultRef.current;
      }
    }

    // Compute new result
    const result = computation();
    lastResultRef.current = result;
    lastDepsRef.current = deps;
    return result;
  }, deps);
}

// Virtual list hook for large lists (logs, messages)
export function useVirtualList<T>({
  items,
  itemHeight,
  containerHeight,
  overscan = 5,
}: {
  items: T[];
  itemHeight: number;
  containerHeight: number;
  overscan?: number;
}) {
  const scrollTop = useRef(0);

  return useMemo(() => {
    const startIndex = Math.max(0, Math.floor(scrollTop.current / itemHeight) - overscan);
    const endIndex = Math.min(
      items.length - 1,
      Math.floor((scrollTop.current + containerHeight) / itemHeight) + overscan
    );

    const visibleItems = items.slice(startIndex, endIndex + 1).map((item, index) => ({
      item,
      index: startIndex + index,
      offsetTop: (startIndex + index) * itemHeight,
    }));

    return {
      visibleItems,
      totalHeight: items.length * itemHeight,
      updateScrollTop: (newScrollTop: number) => {
        scrollTop.current = newScrollTop;
      },
    };
  }, [items, itemHeight, containerHeight, overscan]);
}

// Performance monitoring hook
export function usePerformanceMonitor(name: string) {
  const startTimeRef = useRef<number>();

  const start = useCallback(() => {
    startTimeRef.current = performance.now();
  }, []);

  const end = useCallback(() => {
    if (startTimeRef.current) {
      const duration = performance.now() - startTimeRef.current;
      console.log(`[Performance] ${name}: ${duration.toFixed(2)}ms`);
      startTimeRef.current = undefined;
      return duration;
    }
    return 0;
  }, [name]);

  return { start, end };
}

// Memory monitoring for development
export function useMemoryMonitor() {
  const logMemoryUsage = useCallback(() => {
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      console.log('[Memory]', {
        used: `${(memory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
        total: `${(memory.totalJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
        limit: `${(memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2)} MB`,
      });
    }
  }, []);

  return { logMemoryUsage };
}