import type { ReactNode } from "react";

export interface EmptyStateProps {
  mark?: string;
  title: string;
  hint: string;
  action?: ReactNode;
}

export function EmptyState({ mark = "✦", title, hint, action }: EmptyStateProps): JSX.Element {
  return (
    <div className="empty-state compact-empty">
      <span className="empty-mark" aria-hidden="true">
        {mark}
      </span>
      <strong>{title}</strong>
      <span>{hint}</span>
      {action}
    </div>
  );
}
