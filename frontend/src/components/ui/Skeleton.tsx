"use client";

import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
  variant?: "text" | "circular" | "rectangular";
  width?: string | number;
  height?: string | number;
  animation?: "pulse" | "wave" | "none";
}

export function Skeleton({
  className,
  variant = "text",
  width,
  height,
  animation = "pulse",
}: SkeletonProps) {
  const baseStyles = "bg-gray-200 dark:bg-slate-700";

  const animationStyles = {
    pulse: "animate-pulse",
    wave: "animate-shimmer",
    none: "",
  };

  const variantStyles = {
    text: "rounded",
    circular: "rounded-full",
    rectangular: "rounded-lg",
  };

  const style: React.CSSProperties = {};
  if (width) style.width = typeof width === "number" ? `${width}px` : width;
  if (height) style.height = typeof height === "number" ? `${height}px` : height;

  // Default heights for text variant
  if (variant === "text" && !height) {
    style.height = "1em";
  }

  return (
    <div
      className={cn(
        baseStyles,
        animationStyles[animation],
        variantStyles[variant],
        className
      )}
      style={style}
      role="status"
      aria-label="Loading..."
    />
  );
}

// Pre-built skeleton patterns
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          variant="text"
          width={i === lines - 1 ? "60%" : "100%"}
          height={16}
        />
      ))}
    </div>
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn("p-4 space-y-3", className)}>
      <Skeleton variant="rectangular" height={120} />
      <Skeleton variant="text" width="80%" height={20} />
      <Skeleton variant="text" width="60%" height={16} />
    </div>
  );
}

export function SkeletonAvatar({ size = 40, className }: { size?: number; className?: string }) {
  return (
    <Skeleton
      variant="circular"
      width={size}
      height={size}
      className={className}
    />
  );
}

// Table row skeleton
export function SkeletonTableRow({ columns = 6 }: { columns?: number }) {
  return (
    <tr className="border-b border-gray-200 dark:border-slate-700">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton
            variant="text"
            width={i === 0 ? "80%" : i === 1 ? "100%" : "60%"}
            height={16}
          />
        </td>
      ))}
    </tr>
  );
}

// Full table skeleton
export function SkeletonTable({
  rows = 10,
  columns = 6,
  className,
}: {
  rows?: number;
  columns?: number;
  className?: string;
}) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="min-w-full">
        <thead className="bg-slate-800 dark:bg-slate-900">
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="px-4 py-3">
                <Skeleton variant="text" width="70%" height={14} className="bg-slate-600" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-slate-800">
          {Array.from({ length: rows }).map((_, i) => (
            <SkeletonTableRow key={i} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Preset card skeleton
export function SkeletonPresetCard({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4", className)}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <Skeleton variant="text" width="60%" height={20} />
          <Skeleton variant="text" width="80%" height={14} className="mt-2" />
        </div>
      </div>
      <div className="mt-3 space-y-2">
        <Skeleton variant="text" width="70%" height={14} />
        <Skeleton variant="text" width="50%" height={14} />
        <Skeleton variant="text" width="60%" height={14} />
      </div>
      <div className="mt-4 flex items-center gap-2">
        <Skeleton variant="rectangular" width={70} height={32} />
      </div>
    </div>
  );
}

// Stock detail page skeleton
export function SkeletonStockDetail({ className }: { className?: string }) {
  return (
    <div className={cn("mx-auto max-w-4xl px-4 py-8", className)}>
      {/* Back button */}
      <Skeleton variant="text" width={120} height={20} className="mb-6" />

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <Skeleton variant="text" width={100} height={36} />
          <Skeleton variant="rectangular" width={60} height={28} />
          <Skeleton variant="circular" width={32} height={32} />
        </div>
        <Skeleton variant="text" width="40%" height={24} className="mt-2" />
        <Skeleton variant="text" width="30%" height={16} className="mt-2" />
      </div>

      {/* Price Info Card */}
      <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 mb-6">
        <div className="flex items-baseline gap-4">
          <Skeleton variant="text" width={120} height={40} />
          <Skeleton variant="text" width={80} height={24} />
        </div>
        <div className="mt-4 grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i}>
              <Skeleton variant="text" width="60%" height={12} />
              <Skeleton variant="text" width="80%" height={20} className="mt-1" />
            </div>
          ))}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
            <Skeleton variant="text" width="40%" height={16} className="mb-3" />
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, j) => (
                <div key={j} className="flex justify-between">
                  <Skeleton variant="text" width="30%" height={14} />
                  <Skeleton variant="text" width="20%" height={14} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
