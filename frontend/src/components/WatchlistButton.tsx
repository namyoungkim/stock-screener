"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

interface WatchlistButtonProps {
  companyId: string;
  className?: string;
  size?: "sm" | "md";
}

export function WatchlistButton({
  companyId,
  className,
  size = "md",
}: WatchlistButtonProps) {
  const { session, user } = useAuth();
  const queryClient = useQueryClient();
  const [showTooltip, setShowTooltip] = useState(false);

  const token = session?.access_token;

  // Check if in watchlist
  const { data: watchlistStatus } = useQuery({
    queryKey: ["watchlist-check", companyId],
    queryFn: () => api.checkInWatchlist(token!, companyId),
    enabled: !!token && !!companyId,
  });

  const isInWatchlist = watchlistStatus?.in_watchlist ?? false;

  // Add mutation
  const addMutation = useMutation({
    mutationFn: () => api.addToWatchlist(token!, { company_id: companyId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist-check", companyId] });
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });

  // Remove mutation
  const removeMutation = useMutation({
    mutationFn: () => api.removeFromWatchlist(token!, companyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist-check", companyId] });
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!user) {
      setShowTooltip(true);
      setTimeout(() => setShowTooltip(false), 2000);
      return;
    }

    if (isInWatchlist) {
      removeMutation.mutate();
    } else {
      addMutation.mutate();
    }
  };

  const isLoading = addMutation.isPending || removeMutation.isPending;
  const iconSize = size === "sm" ? "h-4 w-4" : "h-5 w-5";

  return (
    <div className="relative inline-block">
      <button
        onClick={handleClick}
        disabled={isLoading}
        className={cn(
          "transition-colors",
          isInWatchlist
            ? "text-yellow-500 hover:text-yellow-600"
            : "text-gray-400 hover:text-yellow-500",
          isLoading && "opacity-50",
          className
        )}
        title={isInWatchlist ? "Remove from watchlist" : "Add to watchlist"}
      >
        <Star className={cn(iconSize, isInWatchlist && "fill-current")} />
      </button>

      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap z-50">
          Sign in to use watchlist
        </div>
      )}
    </div>
  );
}
