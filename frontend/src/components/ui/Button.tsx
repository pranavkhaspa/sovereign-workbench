import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-ink hover:opacity-90",
  secondary: "border border-line bg-panel-raised text-fg hover:border-accent hover:text-accent",
  danger: "border border-danger bg-[var(--red-a12)] text-danger hover:bg-[var(--red-a24)]",
  ghost: "text-muted hover:text-accent",
};

const SIZES: Record<Size, string> = {
  sm: "h-7 px-2 text-[11px]",
  md: "h-9 px-3.5 text-xs",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  className = "",
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps): JSX.Element {
  return (
    <button
      {...rest}
      type={type}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded font-semibold uppercase tracking-wide transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
    >
      {loading ? (
        <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
      ) : (
        icon
      )}
      {children}
    </button>
  );
}
