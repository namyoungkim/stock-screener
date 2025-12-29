"use client";

interface WatchlistPromptProps {
  onAddToWatchlist: () => void;
  isLoading?: boolean;
}

export function WatchlistPrompt({
  onAddToWatchlist,
  isLoading = false,
}: WatchlistPromptProps) {
  return (
    <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 p-4">
      <div className="flex items-start gap-3">
        <span className="text-blue-500 text-lg">💡</span>
        <div className="flex-1">
          <p className="text-sm text-blue-800 dark:text-blue-300 mb-3">
            워치리스트에 추가하면 상세 투자 분석을 확인할 수 있습니다.
          </p>
          <button
            onClick={onAddToWatchlist}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <svg
                  className="animate-spin h-4 w-4"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                추가 중...
              </>
            ) : (
              <>
                <span>+</span>
                워치리스트에 추가
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
