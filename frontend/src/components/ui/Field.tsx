import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

const FIELD =
  "w-full rounded border border-white/15 bg-ink/70 px-2.5 py-1.5 text-xs text-slate-100 placeholder:text-slate-500 focus:border-accent/70 focus:outline-none focus:ring-1 focus:ring-accent/50 disabled:opacity-50";

const LABEL = "mb-1 block font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function Input({ label, id, className = "", ...rest }: InputProps): JSX.Element {
  const input = <input {...rest} id={id} className={`${FIELD} ${className}`} />;
  return label ? (
    <label htmlFor={id} className="block">
      <span className={LABEL}>{label}</span>
      {input}
    </label>
  ) : (
    input
  );
}

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export function Textarea({ label, id, className = "", ...rest }: TextareaProps): JSX.Element {
  const field = <textarea {...rest} id={id} className={`${FIELD} font-mono leading-relaxed ${className}`} />;
  return label ? (
    <label htmlFor={id} className="block">
      <span className={LABEL}>{label}</span>
      {field}
    </label>
  ) : (
    field
  );
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
}

export function Select({ label, id, className = "", children, ...rest }: SelectProps): JSX.Element {
  const field = (
    <select {...rest} id={id} className={`${FIELD} ${className}`}>
      {children}
    </select>
  );
  return label ? (
    <label htmlFor={id} className="block">
      <span className={LABEL}>{label}</span>
      {field}
    </label>
  ) : (
    field
  );
}
