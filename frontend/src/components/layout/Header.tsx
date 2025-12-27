"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { UserMenu } from "@/components/auth/UserMenu";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

const navigation = [
  { name: "Screener", href: "/" },
  { name: "Presets", href: "/presets" },
  { name: "Watchlist", href: "/watchlist" },
];

export function Header() {
  const pathname = usePathname();

  return (
    <header className="border-b border-slate-200 bg-slate-800 shadow-md">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2">
              <TrendingUp className="h-6 w-6 text-emerald-400" />
              <span className="text-xl font-bold text-white">Stock Screener</span>
            </Link>

            <nav className="hidden md:flex gap-6">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "text-sm font-medium transition-colors hover:text-emerald-400",
                    pathname === item.href
                      ? "text-emerald-400"
                      : "text-slate-300"
                  )}
                >
                  {item.name}
                </Link>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-4">
            <span className="hidden sm:inline text-sm text-slate-300 bg-slate-700 px-3 py-1 rounded-full">
              US & KR Markets
            </span>
            <ThemeToggle />
            <UserMenu />
          </div>
        </div>
      </div>
    </header>
  );
}
