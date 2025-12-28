"use client";

import { X, CheckCircle, XCircle, Info, AlertTriangle } from "lucide-react";
import { useToast, ToastType } from "@/contexts/ToastContext";

const TOAST_ICONS: Record<ToastType, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
};

const TOAST_STYLES: Record<ToastType, string> = {
  success: "bg-emerald-50 dark:bg-emerald-900/30 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200",
  error: "bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200",
  info: "bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-200",
  warning: "bg-amber-50 dark:bg-amber-900/30 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200",
};

const ICON_STYLES: Record<ToastType, string> = {
  success: "text-emerald-500 dark:text-emerald-400",
  error: "text-red-500 dark:text-red-400",
  info: "text-blue-500 dark:text-blue-400",
  warning: "text-amber-500 dark:text-amber-400",
};

export function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2"
      role="region"
      aria-label="Notifications"
      aria-live="polite"
    >
      {toasts.map((toast) => {
        const Icon = TOAST_ICONS[toast.type];
        return (
          <div
            key={toast.id}
            className={`
              flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg
              animate-slide-in-from-right
              ${TOAST_STYLES[toast.type]}
            `}
            role="alert"
          >
            <Icon className={`h-5 w-5 flex-shrink-0 ${ICON_STYLES[toast.type]}`} />
            <p className="text-sm font-medium flex-1">{toast.message}</p>
            <button
              onClick={() => removeToast(toast.id)}
              className="flex-shrink-0 p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
              aria-label="Close notification"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
