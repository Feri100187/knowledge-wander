"use client";

import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

import { prefersReducedMotion } from "@/lib/motion";

interface ProgressiveBookListProps<T> {
  items: T[];
  listKey: string;
  getItemKey: (item: T) => string;
  renderItem: (item: T, index: number) => ReactNode;
  className?: string;
  itemClassName?: string;
  revealInterval?: number;
}

export default function ProgressiveBookList<T>({
  items,
  listKey,
  getItemKey,
  renderItem,
  className,
  itemClassName,
  revealInterval = 160,
}: ProgressiveBookListProps<T>) {
  const [visibleCount, setVisibleCount] = useState(0);
  const reducedMotion = prefersReducedMotion();
  const previousKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const isNewList = previousKeyRef.current !== listKey;
    previousKeyRef.current = listKey;

    if (reducedMotion || isNewList) {
      const immediateTimer = window.setTimeout(() => {
        setVisibleCount(reducedMotion ? items.length : Math.min(1, items.length));
      }, 0);
      return () => window.clearTimeout(immediateTimer);
    }

    if (visibleCount > items.length) {
      const shrinkTimer = window.setTimeout(() => setVisibleCount(items.length), 0);
      return () => window.clearTimeout(shrinkTimer);
    }

    if (items.length === 0 || visibleCount >= items.length) {
      return;
    }

    const timer = window.setInterval(() => {
      setVisibleCount((current) => {
        if (current >= items.length) {
          return current;
        }
        return current + 1;
      });
    }, revealInterval);

    return () => {
      window.clearInterval(timer);
    };
  }, [items.length, listKey, reducedMotion, revealInterval, visibleCount]);

  const visibleItems = items.slice(0, visibleCount);

  return (
    <div className={className}>
      {visibleItems.map((item, index) => {
        const style = {
          "--progressive-index": index,
        } as CSSProperties;
        return (
          <div
            key={getItemKey(item)}
            className={itemClassName}
            style={style}
            data-reveal-index={index}
          >
            {renderItem(item, index)}
          </div>
        );
      })}
    </div>
  );
}
