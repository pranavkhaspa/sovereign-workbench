import type { HTMLAttributes, ReactNode } from "react";

export interface CardProps extends HTMLAttributes<HTMLElement> {
  title?: string;
  kicker?: string;
  action?: ReactNode;
  children: ReactNode;
}

export function Card({
  title,
  kicker,
  action,
  children,
  className = "",
  ...rest
}: CardProps): JSX.Element {
  return (
    <section
      {...rest}
      className={`rounded-md border border-white/10 bg-panel/80 shadow-sm ${className}`}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 border-b border-white/10 px-4 py-3">
          <div>
            {kicker && (
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
                {kicker}
              </div>
            )}
            {title && <h2 className="text-sm font-semibold text-slate-100">{title}</h2>}
          </div>
          {action}
        </header>
      )}
      <div className="px-4 py-3">{children}</div>
    </section>
  );
}
