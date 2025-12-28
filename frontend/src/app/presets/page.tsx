"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Layers, Plus, Trash2, Play } from "lucide-react";
import { api, UserPreset, MetricFilter } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { PresetForm } from "@/components/PresetForm";
import { SkeletonPresetCard } from "@/components/ui/Skeleton";

// Metric label mapping
const METRIC_LABELS: Record<string, string> = {
  pe_ratio: "P/E Ratio",
  pb_ratio: "P/B Ratio",
  ps_ratio: "P/S Ratio",
  ev_ebitda: "EV/EBITDA",
  peg_ratio: "PEG Ratio",
  roe: "ROE",
  roa: "ROA",
  gross_margin: "Gross Margin",
  net_margin: "Net Margin",
  debt_equity: "Debt/Equity",
  current_ratio: "Current Ratio",
  dividend_yield: "Dividend Yield",
  rsi: "RSI",
  mfi: "MFI",
  bb_percent: "Bollinger %B",
  macd: "MACD",
  graham_number: "Graham Number",
  beta: "Beta",
  fifty_two_week_high: "52W High",
  fifty_two_week_low: "52W Low",
};

function formatFilter(filter: MetricFilter): string {
  const label = METRIC_LABELS[filter.metric] || filter.metric;
  return `${label} ${filter.operator} ${filter.value}`;
}

interface PresetCardProps {
  name: string;
  description?: string | null;
  filters: MetricFilter[];
  isSystem?: boolean;
  onApply: () => void;
  onDelete?: () => void;
}

function PresetCard({ name, description, filters, isSystem, onApply, onDelete }: PresetCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 shadow-sm">
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-white">{name}</h3>
          {description && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{description}</p>
          )}
        </div>
        {isSystem && (
          <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded">
            System
          </span>
        )}
      </div>

      <div className="mt-3 space-y-1">
        {filters.map((filter, idx) => (
          <div
            key={idx}
            className="text-sm font-mono text-gray-600 dark:text-gray-300 flex items-center gap-2"
          >
            <span className="text-gray-400 dark:text-gray-500">•</span>
            {formatFilter(filter)}
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={onApply}
          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors"
        >
          <Play className="h-4 w-4" />
          Apply
        </button>
        {!isSystem && onDelete && (
          <button
            onClick={onDelete}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        )}
      </div>
    </div>
  );
}

export default function PresetsPage() {
  const router = useRouter();
  const { session, user } = useAuth();
  const token = session?.access_token;
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  // Fetch system presets
  const { data: systemPresets = [], isLoading: systemLoading } = useQuery({
    queryKey: ["presets"],
    queryFn: api.getPresets,
  });

  // Fetch user presets
  const { data: userPresetsData, isLoading: userLoading } = useQuery({
    queryKey: ["user-presets"],
    queryFn: () => api.getUserPresets(token!),
    enabled: !!token,
  });

  const deleteMutation = useMutation({
    mutationFn: (presetId: string) => api.deleteUserPreset(token!, presetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-presets"] });
    },
  });

  const handleApplyPreset = (presetId: string) => {
    // Navigate to home with preset applied
    router.push(`/?preset=${presetId}`);
  };

  const handleApplyUserPreset = (preset: UserPreset) => {
    // For user presets, we need to apply filters directly
    // Store in sessionStorage and navigate
    sessionStorage.setItem("customFilters", JSON.stringify(preset.filters));
    router.push("/?customPreset=true");
  };

  const userPresets = userPresetsData?.items ?? [];
  const isLoading = systemLoading || (!!token && userLoading);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Preset Strategies</h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          Pre-configured screening strategies for value investing
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-8">
          <section>
            <div className="h-6 w-32 bg-gray-200 dark:bg-slate-700 rounded animate-pulse mb-4" />
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <SkeletonPresetCard key={i} />
              ))}
            </div>
          </section>
          <section>
            <div className="h-6 w-28 bg-gray-200 dark:bg-slate-700 rounded animate-pulse mb-4" />
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-2">
              {Array.from({ length: 2 }).map((_, i) => (
                <SkeletonPresetCard key={i} />
              ))}
            </div>
          </section>
        </div>
      ) : (
        <div className="space-y-8">
          {/* System Presets */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              System Presets
            </h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-2">
              {systemPresets.map((preset) => (
                <PresetCard
                  key={preset.id}
                  name={preset.name}
                  description={preset.description}
                  filters={preset.filters}
                  isSystem
                  onApply={() => handleApplyPreset(preset.id)}
                />
              ))}
            </div>
          </section>

          {/* User Presets */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                My Presets
              </h2>
              {user && (
                <button
                  onClick={() => setShowForm(true)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  Create Preset
                </button>
              )}
            </div>

            {!user ? (
              <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50 p-8 text-center">
                <Layers className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  Sign in to create custom presets
                </h3>
                <p className="text-gray-600 dark:text-gray-400">
                  Save your favorite filter combinations as presets for quick access
                </p>
              </div>
            ) : userPresets.length === 0 ? (
              <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50 p-8 text-center">
                <Layers className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  No custom presets yet
                </h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  Create your first preset to save your favorite filter combinations
                </p>
                <button
                  onClick={() => setShowForm(true)}
                  className="inline-flex items-center gap-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  Create Preset
                </button>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-2">
                {userPresets.map((preset) => (
                  <PresetCard
                    key={preset.id}
                    name={preset.name}
                    description={preset.description}
                    filters={preset.filters}
                    onApply={() => handleApplyUserPreset(preset)}
                    onDelete={() => {
                      if (confirm(`Delete preset "${preset.name}"?`)) {
                        deleteMutation.mutate(preset.id);
                      }
                    }}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* Preset Form Modal */}
      {showForm && token && (
        <PresetForm
          token={token}
          onClose={() => setShowForm(false)}
          onSuccess={() => {
            setShowForm(false);
            queryClient.invalidateQueries({ queryKey: ["user-presets"] });
          }}
        />
      )}
    </div>
  );
}
