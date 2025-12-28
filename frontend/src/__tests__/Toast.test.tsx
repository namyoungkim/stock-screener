import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ToastProvider, useToast } from "@/contexts/ToastContext";
import { ToastContainer } from "@/components/ui/Toast";

// Test component that triggers toasts
function TestComponent() {
  const { success, error, info, warning } = useToast();
  return (
    <div>
      <button onClick={() => success("Success message")}>Show Success</button>
      <button onClick={() => error("Error message")}>Show Error</button>
      <button onClick={() => info("Info message")}>Show Info</button>
      <button onClick={() => warning("Warning message")}>Show Warning</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <ToastProvider>
      <TestComponent />
      <ToastContainer />
    </ToastProvider>
  );
}

describe("Toast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("shows success toast when triggered", () => {
    renderWithProvider();

    fireEvent.click(screen.getByText("Show Success"));

    expect(screen.getByText("Success message")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveClass("bg-emerald-50");
  });

  it("shows error toast when triggered", () => {
    renderWithProvider();

    fireEvent.click(screen.getByText("Show Error"));

    expect(screen.getByText("Error message")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveClass("bg-red-50");
  });

  it("shows info toast when triggered", () => {
    renderWithProvider();

    fireEvent.click(screen.getByText("Show Info"));

    expect(screen.getByText("Info message")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveClass("bg-blue-50");
  });

  it("shows warning toast when triggered", () => {
    renderWithProvider();

    fireEvent.click(screen.getByText("Show Warning"));

    expect(screen.getByText("Warning message")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveClass("bg-amber-50");
  });

  it("removes toast when close button is clicked", () => {
    renderWithProvider();

    fireEvent.click(screen.getByText("Show Success"));
    expect(screen.getByText("Success message")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Close notification"));
    expect(screen.queryByText("Success message")).not.toBeInTheDocument();
  });

  it("auto-removes toast after duration", () => {
    renderWithProvider();

    fireEvent.click(screen.getByText("Show Success"));
    expect(screen.getByText("Success message")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.queryByText("Success message")).not.toBeInTheDocument();
  });

  it("can show multiple toasts", () => {
    renderWithProvider();

    fireEvent.click(screen.getByText("Show Success"));
    fireEvent.click(screen.getByText("Show Error"));

    expect(screen.getByText("Success message")).toBeInTheDocument();
    expect(screen.getByText("Error message")).toBeInTheDocument();
    expect(screen.getAllByRole("alert")).toHaveLength(2);
  });

  it("has proper accessibility attributes", () => {
    renderWithProvider();

    fireEvent.click(screen.getByText("Show Success"));

    const region = screen.getByRole("region");
    expect(region).toHaveAttribute("aria-label", "Notifications");
    expect(region).toHaveAttribute("aria-live", "polite");

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
