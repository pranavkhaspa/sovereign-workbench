import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ModelInfo } from "../api/types";
import { Composer } from "./Composer";

const MODELS: ModelInfo[] = [
  {
    id: "qwen2.5:3b-instruct",
    label: "Qwen2.5 3B Instruct",
    provider: "ollama",
    remote: false,
    tier: "min",
    capabilities: ["plan", "chat"],
    available: true,
    size_hint: "1.9 GB",
    notes: null,
  },
  {
    id: "qwen2.5-coder:3b",
    label: "Qwen2.5 Coder 3B",
    provider: "ollama",
    remote: false,
    tier: "min",
    capabilities: ["code"],
    available: true,
    size_hint: "1.9 GB",
    notes: null,
  },
  {
    id: "moondream2",
    label: "Moondream2",
    provider: "ollama",
    remote: false,
    tier: "min",
    capabilities: ["vision"],
    available: false,
    size_hint: "1.8 GB",
    notes: null,
  },
  {
    id: "bge-small-en-v1.5",
    label: "BGE Small EN v1.5",
    provider: "sentence-transformers",
    remote: false,
    tier: "min",
    capabilities: ["embed"],
    available: true,
    size_hint: "130 MB",
    notes: null,
  },
  {
    id: "gpt-4o-mini",
    label: "GPT-4o mini",
    provider: "openai",
    remote: true,
    tier: "remote",
    capabilities: ["chat", "vision"],
    available: false,
    size_hint: null,
    notes: null,
  },
];

function renderComposer(): ReturnType<typeof render> {
  return render(
    <Composer
      models={MODELS}
      documents={[]}
      running={false}
      onSubmit={vi.fn()}
    />,
  );
}

describe("Composer model picker", () => {
  it("groups models by capability, remote last", () => {
    const { container } = renderComposer();
    const select = container.querySelector<HTMLSelectElement>("#model-select");
    expect(select).not.toBeNull();

    const groups = Array.from(select?.querySelectorAll("optgroup") ?? []);
    expect(groups.map((group) => group.label)).toEqual([
      "CODE",
      "VISION / MULTIMODAL",
      "EMBEDDINGS",
      "GENERAL / REASONING",
      "REMOTE PROVIDERS",
    ]);
    expect(groups[0]?.querySelectorAll("option")).toHaveLength(1);
    expect(groups[4]?.querySelectorAll("option")).toHaveLength(1);
  });

  it("defaults to router auto-selection", () => {
    const { container } = renderComposer();
    const select = container.querySelector<HTMLSelectElement>("#model-select");
    expect(select?.value).toBe("");
    expect(select?.querySelector("option")?.textContent).toBe("AUTO · ROUTER DECIDES");
  });

  it("disables models that are offline or blocked by air-gap", () => {
    const { container } = renderComposer();
    const options = Array.from(
      container.querySelectorAll<HTMLOptionElement>("#model-select option"),
    );
    const optionFor = (needle: string): HTMLOptionElement | undefined =>
      options.find((option) => option.textContent?.includes(needle));

    expect(optionFor("Qwen2.5 Coder")?.disabled).toBe(false);
    expect(optionFor("Moondream2")?.disabled).toBe(true);
    expect(optionFor("Moondream2")?.textContent).toContain("OFFLINE");
    expect(optionFor("GPT-4o mini")?.disabled).toBe(true);
    expect(optionFor("GPT-4o mini")?.textContent).toContain("BLOCKED BY AIR-GAP");
  });

  it("states the air-gap posture next to the picker", () => {
    renderComposer();
    expect(screen.getByText(/air-gap on · remote providers disabled/)).toBeInTheDocument();
  });

  it("labels the prompt box for the / shortcut", () => {
    renderComposer();
    expect(document.getElementById("task-prompt")).not.toBeNull();
    expect(document.getElementById("model-select")).not.toBeNull();
  });

  it("keeps the source picker usable only when documents exist", () => {
    renderComposer();
    const select = document.querySelector<HTMLSelectElement>("#document-select");
    expect(select?.disabled).toBe(true);
  });
});
