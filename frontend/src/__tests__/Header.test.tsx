import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Header } from "@/components/layout/Header";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { AuthProvider } from "@/contexts/AuthContext";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

// Wrapper with all required providers
function renderWithProviders(ui: React.ReactElement) {
  return render(
    <ThemeProvider>
      <AuthProvider>{ui}</AuthProvider>
    </ThemeProvider>
  );
}

describe("Header", () => {
  describe("Desktop navigation", () => {
    it("should show navigation links on desktop", () => {
      renderWithProviders(<Header />);

      expect(screen.getByText("Screener")).toBeInTheDocument();
      expect(screen.getByText("Presets")).toBeInTheDocument();
      expect(screen.getByText("Watchlist")).toBeInTheDocument();
      expect(screen.getByText("Alerts")).toBeInTheDocument();
    });

    it("should show logo", () => {
      renderWithProviders(<Header />);

      expect(screen.getByText("Stock Screener")).toBeInTheDocument();
    });
  });

  describe("Mobile navigation", () => {
    it("should have mobile menu button visible", () => {
      renderWithProviders(<Header />);

      // The mobile menu button should exist (with aria-label)
      const mobileMenuButton = screen.getByRole("button", {
        name: /open menu/i,
      });

      expect(mobileMenuButton).toBeInTheDocument();
    });

    it("should toggle mobile menu when button is clicked", () => {
      renderWithProviders(<Header />);

      const mobileMenuButton = screen.getByRole("button", { name: /open menu/i });

      // Initially menu should be closed
      expect(screen.queryByRole("navigation", { name: /mobile/i })).not.toBeInTheDocument();

      // Click to open
      fireEvent.click(mobileMenuButton);
      expect(screen.getByRole("navigation", { name: /mobile/i })).toBeInTheDocument();

      // Button label should change
      expect(screen.getByRole("button", { name: /close menu/i })).toBeInTheDocument();

      // Click to close
      fireEvent.click(screen.getByRole("button", { name: /close menu/i }));
      expect(screen.queryByRole("navigation", { name: /mobile/i })).not.toBeInTheDocument();
    });

    it("should show all navigation links in mobile menu", () => {
      renderWithProviders(<Header />);

      const mobileMenuButton = screen.getByRole("button", { name: /open menu/i });
      fireEvent.click(mobileMenuButton);

      const mobileNav = screen.getByRole("navigation", { name: /mobile/i });

      expect(mobileNav).toHaveTextContent("Screener");
      expect(mobileNav).toHaveTextContent("Presets");
      expect(mobileNav).toHaveTextContent("Watchlist");
      expect(mobileNav).toHaveTextContent("Alerts");
    });

    it("should close mobile menu when a link is clicked", () => {
      renderWithProviders(<Header />);

      const mobileMenuButton = screen.getByRole("button", { name: /open menu/i });
      fireEvent.click(mobileMenuButton);

      const mobileNav = screen.getByRole("navigation", { name: /mobile/i });
      const presetsLink = mobileNav.querySelector('a[href="/presets"]');

      if (presetsLink) {
        fireEvent.click(presetsLink);
      }

      expect(screen.queryByRole("navigation", { name: /mobile/i })).not.toBeInTheDocument();
    });
  });
});
