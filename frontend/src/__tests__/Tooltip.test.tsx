import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Tooltip } from "@/components/ui/Tooltip";

describe("Tooltip", () => {
  it("renders children correctly", () => {
    render(
      <Tooltip content="Tooltip text">
        <span>Hover me</span>
      </Tooltip>
    );

    expect(screen.getByText("Hover me")).toBeInTheDocument();
  });

  it("shows tooltip on mouse enter", async () => {
    render(
      <Tooltip content="Tooltip text">
        <span>Hover me</span>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me");
    fireEvent.mouseEnter(trigger.parentElement!);

    expect(screen.getByText("Tooltip text")).toBeInTheDocument();
  });

  it("hides tooltip on mouse leave", () => {
    render(
      <Tooltip content="Tooltip text">
        <span>Hover me</span>
      </Tooltip>
    );

    const trigger = screen.getByText("Hover me");
    fireEvent.mouseEnter(trigger.parentElement!);
    expect(screen.getByText("Tooltip text")).toBeInTheDocument();

    fireEvent.mouseLeave(trigger.parentElement!);
    expect(screen.queryByText("Tooltip text")).not.toBeInTheDocument();
  });

  it("does not show tooltip initially", () => {
    render(
      <Tooltip content="Tooltip text">
        <span>Hover me</span>
      </Tooltip>
    );

    expect(screen.queryByText("Tooltip text")).not.toBeInTheDocument();
  });
});
