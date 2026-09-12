import { forwardRef, useEffect, useLayoutEffect, useRef, type ReactNode } from 'react';
import { Info, Warning, Check } from './icons';

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'quiet';
  size?: 'md' | 'lg' | 'xl';
  loading?: boolean;
  icon?: ReactNode;
  iconRight?: ReactNode;
};

export function Button({
  variant = 'secondary', size = 'md', loading = false, icon, iconRight,
  children, className = '', disabled, ...rest
}: ButtonProps) {
  return <button type="button" disabled={disabled || loading}
    className={`btn btn-${variant} btn-${size} ${loading ? 'is-loading' : ''} ${className}`}
    aria-busy={loading || undefined} {...rest}>
    {icon && <span className="btn-icon">{icon}</span>}
    <span className="btn-label">{children}</span>
    {iconRight && <span className="btn-icon">{iconRight}</span>}
    {loading && <span className="btn-spinner" aria-hidden="true" />}
  </button>;
}

export function Spinner({ label }: { label?: string }) {
  return <span className="spinner" role="status">
    <span className="spinner-ring" aria-hidden="true" />
    {label && <span>{label}</span>}
  </span>;
}

type Tone = 'info' | 'warn' | 'error' | 'success';

const TONE_ICON: Record<Tone, ReactNode> = {
  info: <Info size={18} />, warn: <Warning size={18} />,
  error: <Warning size={18} />, success: <Check size={18} />,
};

export function Callout({ tone = 'info', title, children, action, live }: {
  tone?: Tone; title: ReactNode; children?: ReactNode; action?: ReactNode;
  live?: 'polite' | 'assertive';
}) {
  return <div className={`callout callout-${tone}`}
    role={tone === 'error' ? 'alert' : undefined}
    aria-live={live}>
    <span className="callout-icon" aria-hidden="true">{TONE_ICON[tone]}</span>
    <div className="callout-text">
      <p className="callout-title">{title}</p>
      {children && <div className="callout-body">{children}</div>}
    </div>
    {action && <div className="callout-action">{action}</div>}
  </div>;
}

export function Badge({ tone = 'neutral', children, title }: {
  tone?: 'neutral' | 'accent' | 'warn' | 'good'; children: ReactNode; title?: string;
}) {
  return <span className={`badge badge-${tone}`} title={title}>{children}</span>;
}

export function Field({ id, label, hint, required, highlight, children }: {
  id: string; label: ReactNode; hint?: ReactNode; required?: boolean;
  highlight?: boolean; children: ReactNode;
}) {
  return <div className={`field ${highlight ? 'is-highlighted' : ''}`}>
    <label className="field-label" htmlFor={id}>
      {label}
      {required && <span className="field-required" title="Обязательный реквизит"> *</span>}
    </label>
    {children}
    {hint && <p className="field-hint">{hint}</p>}
  </div>;
}

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  minRows?: number; maxRows?: number;
};

/** Grows with its content instead of showing an inner scrollbar. */
export const AutoTextarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function AutoTextarea({ minRows = 8, maxRows = 26, className = '', value, ...rest }, ref) {
    const inner = useRef<HTMLTextAreaElement>(null);
    useLayoutEffect(() => {
      const node = inner.current;
      if (!node) return;
      const style = window.getComputedStyle(node);
      const line = parseFloat(style.lineHeight) || 24;
      const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      // scrollHeight excludes the border, but the box is sized with it: add it back or the
      // field ends up a couple of pixels short and grows an inner scrollbar.
      const border = parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
      node.style.height = 'auto';
      const content = Math.min(
        Math.max(node.scrollHeight, line * minRows + padding), line * maxRows + padding,
      );
      node.style.height = `${content + border}px`;
    }, [value, minRows, maxRows]);
    return <textarea ref={node => {
      inner.current = node;
      if (typeof ref === 'function') ref(node);
      else if (ref) ref.current = node;
    }} className={`textarea ${className}`} value={value} {...rest} />;
  },
);

export function Toast({ message, tone = 'info', onDone }: {
  message: string; tone?: Tone; onDone: () => void;
}) {
  useEffect(() => {
    const timer = window.setTimeout(onDone, 5_000);
    return () => window.clearTimeout(timer);
  }, [message, onDone]);
  return <div className={`toast toast-${tone}`} role="status">
    <span className="toast-icon" aria-hidden="true">{TONE_ICON[tone]}</span>
    <span>{message}</span>
  </div>;
}

export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: ReactNode; title?: string }[];
  onChange: (value: T) => void; label: string;
}) {
  return <div className="segmented" role="group" aria-label={label}>
    {options.map(option => <button key={option.value} type="button" title={option.title}
      className={`segmented-item ${option.value === value ? 'is-active' : ''}`}
      aria-pressed={option.value === value}
      onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>;
}
