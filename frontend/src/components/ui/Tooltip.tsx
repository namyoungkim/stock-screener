"use client";

import { ReactNode, useState, useRef, useEffect } from "react";

interface TooltipProps {
  content: string;
  children: ReactNode;
  position?: "top" | "bottom";
}

export function Tooltip({ content, children, position = "top" }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [coords, setCoords] = useState({ x: 0, y: 0 });
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (isVisible && triggerRef.current && tooltipRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();

      let x = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2;
      let y = position === "top"
        ? triggerRect.top - tooltipRect.height - 8
        : triggerRect.bottom + 8;

      // Prevent going off-screen horizontally
      if (x < 8) x = 8;
      if (x + tooltipRect.width > window.innerWidth - 8) {
        x = window.innerWidth - tooltipRect.width - 8;
      }

      // Prevent going off-screen vertically
      if (y < 8) y = triggerRect.bottom + 8;
      if (y + tooltipRect.height > window.innerHeight - 8) {
        y = triggerRect.top - tooltipRect.height - 8;
      }

      setCoords({ x, y });
    }
  }, [isVisible, position]);

  return (
    <span
      ref={triggerRef}
      className="inline-flex items-center cursor-help"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children}
      {isVisible && (
        <span
          ref={tooltipRef}
          className="fixed z-[9999] px-3 py-2 rounded-lg bg-slate-800 text-white text-xs font-medium shadow-lg"
          style={{
            left: coords.x,
            top: coords.y,
            maxWidth: "280px",
            pointerEvents: "none",
          }}
        >
          {content}
        </span>
      )}
    </span>
  );
}
