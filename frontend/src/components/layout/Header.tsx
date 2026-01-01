"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { UserMenu } from "@/components/auth/UserMenu";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

const navigation = [
  { name: "Screener", href: "/" },
  { name: "Presets", href: "/presets" },
  { name: "Watchlist", href: "/watchlist" },
  { name: "Alerts", href: "/alerts" },
];

export function Header() {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const closeMobileMenu = () => setIsMobileMenuOpen(false);

  return (
    <header className="border-b border-slate-200 bg-slate-800 shadow-md">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2">
              <TrendingUp className="h-6 w-6 text-emerald-400" />
              <span className="text-xl font-bold text-white">Stock Screener</span>
            </Link>

            {/* Desktop navigation */}
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

            {/* Mobile menu button */}
            <button
              type="button"
              className="md:hidden p-2 text-slate-300 hover:text-white transition-colors"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
              aria-expanded={isMobileMenuOpen}
            >
              {isMobileMenuOpen ? (
                <X className="h-6 w-6" />
              ) : (
                <Menu className="h-6 w-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile navigation */}
        {isMobileMenuOpen && (
          <nav
            className="md:hidden border-t border-slate-700 py-4"
            aria-label="Mobile navigation"
          >
            <div className="flex flex-col gap-2">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  href={item.href}
                  onClick={closeMobileMenu}
                  className={cn(
                    "px-4 py-2 text-base font-medium rounded-lg transition-colors",
                    pathname === item.href
                      ? "text-emerald-400 bg-slate-700"
                      : "text-slate-300 hover:text-white hover:bg-slate-700"
                  )}
                >
                  {item.name}
                </Link>
              ))}
            </div>
          </nav>
        )}
      </div>
    </header>
  );
}
