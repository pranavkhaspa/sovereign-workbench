import type { ReactNode } from "react";

type Tone = "neutral" | "accent" | "ok" | "warn" | "danger";

export interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
}

const TONES: Record<Tone, string> = {
  neutral: "border-line text-muted",
  accent: "border-accent text-accent bg-[var(--cyan-a12)]",
  ok: "border-ok text-ok bg-[var(--green-a12)]",
  warn: "border-warn text-warn bg-[var(--orange-a12)]",
  danger: "border-danger text-danger bg-[var(--red-a12)]",
};

export function Badge({ tone = "neutral", children }: BadgeProps): JSX.Element {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
