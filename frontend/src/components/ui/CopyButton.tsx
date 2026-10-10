import { useState } from "react";

import { Button } from "./Button";

export interface CopyButtonProps {
  value: string;
  label?: string;
  size?: "sm" | "md";
  className?: string;
}

export function CopyButton({
  value,
  label = "Copy",
  size = "sm",
  className = "",
}: CopyButtonProps): JSX.Element {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  const copy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(value);
      setState("copied");
    } catch {
      setState("failed");
    }
    window.setTimeout(() => setState("idle"), 1800);
  };

  return (
    <Button size={size} className={className} onClick={() => void copy()}>
      {state === "copied" ? "Copied" : state === "failed" ? "Copy failed" : label}
    </Button>
  );
}
