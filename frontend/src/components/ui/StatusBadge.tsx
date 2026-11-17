interface StatusBadgeProps {
  variant: 'ok' | 'warn' | 'error' | 'neutral'
  children: string
}

export function StatusBadge({ variant, children }: StatusBadgeProps) {
  return <span className={`badge badge--${variant}`}>{children}</span>
}