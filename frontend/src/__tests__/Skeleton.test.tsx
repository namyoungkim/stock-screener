import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Skeleton,
  SkeletonText,
  SkeletonCard,
  SkeletonAvatar,
  SkeletonTableRow,
  SkeletonTable,
} from "@/components/ui/Skeleton";

describe("Skeleton", () => {
  it("renders with default props", () => {
    render(<Skeleton />);
    const skeleton = screen.getByRole("status");
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveAttribute("aria-label", "Loading...");
  });

  it("applies pulse animation by default", () => {
    render(<Skeleton />);
    expect(screen.getByRole("status")).toHaveClass("animate-pulse");
  });

  it("applies text variant styles", () => {
    render(<Skeleton variant="text" />);
    expect(screen.getByRole("status")).toHaveClass("rounded");
  });

  it("applies circular variant styles", () => {
    render(<Skeleton variant="circular" />);
    expect(screen.getByRole("status")).toHaveClass("rounded-full");
  });

  it("applies rectangular variant styles", () => {
    render(<Skeleton variant="rectangular" />);
    expect(screen.getByRole("status")).toHaveClass("rounded-lg");
  });

  it("applies custom width and height", () => {
    render(<Skeleton width={100} height={50} />);
    const skeleton = screen.getByRole("status");
    expect(skeleton).toHaveStyle({ width: "100px", height: "50px" });
  });

  it("accepts string dimensions", () => {
    render(<Skeleton width="50%" height="2rem" />);
    const skeleton = screen.getByRole("status");
    expect(skeleton).toHaveStyle({ width: "50%", height: "2rem" });
  });

  it("applies custom className", () => {
    render(<Skeleton className="my-custom-class" />);
    expect(screen.getByRole("status")).toHaveClass("my-custom-class");
  });
});

describe("SkeletonText", () => {
  it("renders default 3 lines", () => {
    render(<SkeletonText />);
    const skeletons = screen.getAllByRole("status");
    expect(skeletons).toHaveLength(3);
  });

  it("renders custom number of lines", () => {
    render(<SkeletonText lines={5} />);
    const skeletons = screen.getAllByRole("status");
    expect(skeletons).toHaveLength(5);
  });
});

describe("SkeletonCard", () => {
  it("renders card skeleton with image and text placeholders", () => {
    render(<SkeletonCard />);
    const skeletons = screen.getAllByRole("status");
    expect(skeletons.length).toBeGreaterThanOrEqual(3);
  });
});

describe("SkeletonAvatar", () => {
  it("renders circular avatar skeleton", () => {
    render(<SkeletonAvatar />);
    const skeleton = screen.getByRole("status");
    expect(skeleton).toHaveClass("rounded-full");
  });

  it("applies custom size", () => {
    render(<SkeletonAvatar size={60} />);
    const skeleton = screen.getByRole("status");
    expect(skeleton).toHaveStyle({ width: "60px", height: "60px" });
  });
});

describe("SkeletonTableRow", () => {
  it("renders default 6 columns", () => {
    render(
      <table>
        <tbody>
          <SkeletonTableRow />
        </tbody>
      </table>
    );
    const cells = screen.getAllByRole("cell");
    expect(cells).toHaveLength(6);
  });

  it("renders custom number of columns", () => {
    render(
      <table>
        <tbody>
          <SkeletonTableRow columns={4} />
        </tbody>
      </table>
    );
    const cells = screen.getAllByRole("cell");
    expect(cells).toHaveLength(4);
  });
});

describe("SkeletonTable", () => {
  it("renders table with header and body", () => {
    render(<SkeletonTable rows={5} columns={4} />);

    // Header columns
    const headerCells = screen.getAllByRole("columnheader");
    expect(headerCells).toHaveLength(4);

    // Body rows (5 rows * 4 columns = 20 cells)
    const bodyCells = screen.getAllByRole("cell");
    expect(bodyCells).toHaveLength(20);
  });

  it("renders default 10 rows and 6 columns", () => {
    render(<SkeletonTable />);

    const headerCells = screen.getAllByRole("columnheader");
    expect(headerCells).toHaveLength(6);

    const bodyCells = screen.getAllByRole("cell");
    expect(bodyCells).toHaveLength(60); // 10 rows * 6 columns
  });
});
