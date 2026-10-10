interface SpinnerProps {
  label?: string;
}

export function Spinner({ label }: SpinnerProps = {}): JSX.Element {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted">
      <span
        className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
        aria-hidden="true"
      />
      {label ? <span>{label}</span> : <span className="sr-only">Loading</span>}
    </span>
  );
}
