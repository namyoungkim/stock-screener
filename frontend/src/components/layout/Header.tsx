"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Screener", href: "/" },
  { name: "Presets", href: "/presets" },
];

export function Header() {
  const pathname = usePathname();

  return (
    <header className="border-b bg-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2">
              <TrendingUp className="h-6 w-6 text-blue-600" />
              <span className="text-xl font-bold">Stock Screener</span>
            </Link>

            <nav className="hidden md:flex gap-6">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "text-sm font-medium transition-colors hover:text-blue-600",
                    pathname === item.href
                      ? "text-blue-600"
                      : "text-gray-600"
                  )}
                >
                  {item.name}
                </Link>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">US & KR Markets</span>
          </div>
        </div>
      </div>
    </header>
  );
}
