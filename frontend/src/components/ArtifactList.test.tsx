import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Artifact } from "../api/types";
import { ArtifactList } from "./ArtifactList";

const ARTIFACTS: Artifact[] = [
  {
    id: "art-1",
    task_id: "task-1",
    filename: "Approval-Note-Unit12.docx",
    kind: "docx",
    size_bytes: 49_360,
    created_at: "2026-10-09T11:03:22.000Z",
  },
  {
    id: "art-2",
    task_id: "task-1",
    filename: "analyze_units.py",
    kind: "code",
    size_bytes: 3_184,
    created_at: "2026-10-09T11:05:41.000Z",
  },
];

describe("ArtifactList", () => {
  it("shows a loading row while the list is fetching", () => {
    render(<ArtifactList artifacts={[]} loading />);
    expect(screen.getByText(/Loading deliverables/)).toBeInTheDocument();
  });

  it("shows the failure message with the backend detail", () => {
    render(<ArtifactList artifacts={[]} error="artifact store offline" />);
    expect(screen.getByText("Could not load artifacts: artifact store offline")).toBeInTheDocument();
  });

  it("distinguishes a fresh workspace from a run that produced nothing", () => {
    const { rerender } = render(<ArtifactList artifacts={[]} />);
    expect(screen.getByText("No deliverables yet")).toBeInTheDocument();

    rerender(<ArtifactList artifacts={[]} taskId="task-1" />);
    expect(screen.getByText("No deliverables for this run")).toBeInTheDocument();
  });

  it("lists every artifact with preview and download affordances", () => {
    render(<ArtifactList artifacts={ARTIFACTS} taskId="task-1" />);
    expect(screen.getByText("Approval-Note-Unit12.docx")).toBeInTheDocument();
    expect(screen.getByText("analyze_units.py")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Preview" })).toHaveLength(2);

    const download = screen.getByRole("link", { name: "Download Approval-Note-Unit12.docx" });
    expect(download).toHaveAttribute("href", "/api/artifacts/art-1/download");
    expect(download).toHaveAttribute("download", "Approval-Note-Unit12.docx");
  });
});
