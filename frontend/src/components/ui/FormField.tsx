import type { ReactNode } from "react";

interface FormFieldProps {
  label: string;
  htmlFor: string;
  error?: string | null;
  hint?: string;
  children: ReactNode;
}

export function FormField({ label, htmlFor, error, hint, children }: FormFieldProps) {
  return (
    <div className="bv-field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && !error ? <span className="bv-field__hint">{hint}</span> : null}
      {error ? (
        <span className="bv-field__error" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}