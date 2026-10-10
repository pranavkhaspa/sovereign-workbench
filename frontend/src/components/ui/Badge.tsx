import type { ReactNode } from "react";

type Tone = "neutral" | "accent" | "ok" | "warn" | "danger";

export interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
}

const TONES: Record<Tone, string> = {
  neutral: "border-white/15 bg-white/5 text-slate-300",
  accent: "border-accent/50 bg-accent/10 text-accent",
  ok: "border-ok/50 bg-ok/10 text-ok",
  warn: "border-warn/50 bg-warn/10 text-warn",
  danger: "border-danger/50 bg-danger/10 text-danger",
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
