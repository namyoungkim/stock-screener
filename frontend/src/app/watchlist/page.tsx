"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Star } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { WatchlistButton } from "@/components/WatchlistButton";

export default function WatchlistPage() {
  const { session, user, isLoading: authLoading } = useAuth();
  const token = session?.access_token;

  const {
    data: watchlistData,
    isLoading,
  } = useQuery({
    queryKey: ["watchlist"],
    queryFn: () => api.getWatchlist(token!, { limit: 100 }),
    enabled: !!token,
  });

  // Not logged in
  if (!authLoading && !user) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <Star className="mx-auto h-16 w-16 text-gray-300 mb-4" />
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Sign in to view your watchlist
        </h1>
        <p className="text-gray-600 mb-6">
          Track your favorite stocks and set price targets
        </p>
      </div>
    );
  }

  // Loading
  if (authLoading || isLoading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="flex items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
        </div>
      </div>
    );
  }

  const items = watchlistData?.items ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">My Watchlist</h1>
        <p className="mt-2 text-slate-600">
          {items.length} {items.length === 1 ? "stock" : "stocks"} tracked
        </p>
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-12 text-center">
          <Star className="mx-auto h-12 w-12 text-gray-300 mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Your watchlist is empty
          </h2>
          <p className="text-gray-600 mb-6">
            Browse stocks and click the star icon to add them here
          </p>
          <Link
            href="/"
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Browse Stocks
          </Link>
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-slate-800">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-white">
                  Stock
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-white">
                  Market
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase text-white">
                  Target Price
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-white">
                  Notes
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-white">
                  Added
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase text-white">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-4">
                    <Link
                      href={`/stocks/${item.ticker}?market=${item.market}`}
                      className="font-bold text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {item.ticker}
                    </Link>
                    <p className="text-sm text-gray-500 truncate max-w-[200px]">
                      {item.name}
                    </p>
                  </td>
                  <td className="px-4 py-4">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                        item.market === "US"
                          ? "bg-blue-100 text-blue-800"
                          : item.market === "KOSPI"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-purple-100 text-purple-800"
                      }`}
                    >
                      {item.market}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-right">
                    {item.target_price ? (
                      <span className="font-medium text-gray-900">
                        ${item.target_price.toLocaleString()}
                      </span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <p className="text-sm text-gray-600 truncate max-w-[200px]">
                      {item.notes || "-"}
                    </p>
                  </td>
                  <td className="px-4 py-4 text-sm text-gray-500">
                    {new Date(item.added_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-4 text-center">
                    <WatchlistButton companyId={item.company_id} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
