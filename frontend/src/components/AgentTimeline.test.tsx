import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TimelineEntry } from "../store/useWorkbench";
import { AgentTimeline } from "./AgentTimeline";

const ENTRIES: TimelineEntry[] = [
  {
    id: "ev-1",
    type: "plan",
    label: "Retrieve excerpts, then draft the approval note",
    detail: "model qwen2.5:3b-instruct · capability chat",
    data: { model_id: "qwen2.5:3b-instruct" },
    at: "2026-10-09T10:00:00.000Z",
  },
  {
    id: "ev-2",
    type: "tool_call",
    label: "doc_search",
    data: { tool: "doc_search", args: { top_k: 3 } },
    at: "2026-10-09T10:00:01.500Z",
  },
  {
    id: "ev-3",
    type: "error",
    label: "Tool returned no rows",
    detail: "permission denied on /var/lib/sovereign/index",
    data: {},
    at: "2026-10-09T10:00:03.000Z",
  },
];

describe("AgentTimeline", () => {
  it("shows an empty state before any event arrives", () => {
    render(<AgentTimeline entries={[]} streamState="idle" />);
    expect(screen.getByText("Trajectory is clear")).toBeInTheDocument();
    expect(screen.getByText("awaiting task")).toBeInTheDocument();
  });

  it("renders a distinct row per event type with the stream state", () => {
    render(<AgentTimeline entries={ENTRIES} streamState="streaming" />);
    expect(screen.getByText("live execution")).toBeInTheDocument();
    expect(screen.getByText("03 events")).toBeInTheDocument();
    expect(screen.getByText("plan")).toBeInTheDocument();
    expect(screen.getByText("tool call")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
    expect(
      screen.getByText("Retrieve excerpts, then draft the approval note"),
    ).toBeInTheDocument();
  });

  it("marks error rows with the danger tone", () => {
    render(<AgentTimeline entries={ENTRIES} streamState="streaming" />);
    const label = screen.getByText("error");
    expect(label.closest("li")?.classList.contains("timeline-danger")).toBe(true);
    const plan = screen.getByText("plan");
    expect(plan.closest("li")?.classList.contains("timeline-accent")).toBe(true);
  });

  it("reports elapsed time from the first event", () => {
    render(<AgentTimeline entries={ENTRIES} streamState="streaming" />);
    expect(screen.getByText("+0ms")).toBeInTheDocument();
    expect(screen.getByText("+1.5s")).toBeInTheDocument();
    expect(screen.getByText("+3.0s")).toBeInTheDocument();
  });

  it("expands a row into a copyable detail block", () => {
    render(<AgentTimeline entries={ENTRIES} streamState="streaming" />);
    expect(screen.queryByRole("button", { name: "Copy" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("model qwen2.5:3b-instruct · capability chat"));

    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
    expect(
      screen.getByText("model qwen2.5:3b-instruct · capability chat", { selector: "pre" }),
    ).toBeInTheDocument();
  });

  it("collapses the detail block again on a second click", () => {
    render(<AgentTimeline entries={ENTRIES} streamState="complete" />);
    const toggle = (): HTMLElement => {
      const matches = screen.getAllByText("model qwen2.5:3b-instruct · capability chat");
      const insideButton = matches.find((match) => match.closest("button"));
      if (!insideButton) throw new Error("detail toggle not found");
      return insideButton;
    };
    fireEvent.click(toggle());
    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
    fireEvent.click(toggle());
    expect(screen.queryByRole("button", { name: "Copy" })).not.toBeInTheDocument();
  });
});
