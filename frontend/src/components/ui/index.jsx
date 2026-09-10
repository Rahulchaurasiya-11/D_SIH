/**
 * UI primitives.
 *
 * Small, unopinionated building blocks that every screen composes from, so
 * spacing, radii, focus rings and status colours stay consistent without each
 * screen re-deciding them.
 */

import clsx from 'clsx';
import { AlertCircle, Check, ChevronDown, Loader2, X } from 'lucide-react';
import { useEffect, useRef } from 'react';

/* --------------------------------------------------------------------------- */
/* Button                                                                       */
/* --------------------------------------------------------------------------- */

const BUTTON_VARIANTS = {
  primary: 'bg-brand text-brand-ink hover:bg-brand/90 active:bg-brand/95 shadow-card',
  secondary: 'bg-surface text-ink border border-line hover:bg-raised',
  ghost: 'text-muted hover:text-ink hover:bg-raised',
  danger: 'bg-bad text-white hover:bg-bad/90',
  subtle: 'bg-brand-soft text-brand hover:bg-brand-soft/70',
};

const BUTTON_SIZES = {
  sm: 'h-8 px-3 text-[13px] gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
  lg: 'h-12 px-6 text-[15px] gap-2',
  icon: 'h-9 w-9',
};

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon: Icon,
  className,
  children,
  disabled,
  ...props
}) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center rounded font-medium transition-colors',
        'disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap',
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin shrink-0" aria-hidden />
      ) : (
        Icon && <Icon className="h-4 w-4 shrink-0" aria-hidden />
      )}
      {children}
    </button>
  );
}

/* --------------------------------------------------------------------------- */
/* Card                                                                         */
/* --------------------------------------------------------------------------- */

export function Card({ className, children, ...props }) {
  return (
    <div className={clsx('card', className)} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action, className }) {
  return (
    <div className={clsx('flex items-start justify-between gap-4 px-5 py-4 border-b border-line', className)}>
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold text-ink leading-tight">{title}</h2>
        {subtitle && <p className="text-[13px] text-muted mt-0.5">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function CardBody({ className, children }) {
  return <div className={clsx('p-5', className)}>{children}</div>;
}

/* --------------------------------------------------------------------------- */
/* Badge                                                                        */
/* --------------------------------------------------------------------------- */

const BADGE_TONES = {
  neutral: 'bg-raised text-muted',
  brand: 'bg-brand-soft text-brand',
  ok: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  bad: 'bg-bad-soft text-bad',
};

export function Badge({ tone = 'neutral', className, children, icon: Icon }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold',
        'uppercase tracking-wide',
        BADGE_TONES[tone],
        className,
      )}
    >
      {Icon && <Icon className="h-3 w-3" aria-hidden />}
      {children}
    </span>
  );
}

/** Maps a compliance status to its tone once, so no screen re-derives it. */
export function statusTone(status) {
  if (status === 'COMPLIANT') return 'ok';
  if (status === 'PARTIALLY_COMPLIANT') return 'warn';
  return 'bad';
}

export function severityTone(severity) {
  const value = String(severity || '').toUpperCase();
  if (value === 'CRITICAL' || value === 'HIGH') return 'bad';
  if (value === 'MEDIUM' || value === 'LOW') return 'warn';
  return 'neutral';
}

/* --------------------------------------------------------------------------- */
/* Form fields                                                                  */
/* --------------------------------------------------------------------------- */

const FIELD_BASE =
  'w-full rounded border border-line bg-surface px-3 text-sm text-ink placeholder:text-faint ' +
  'transition-colors focus:border-brand disabled:opacity-60';

export function Field({ label, hint, error, children, className, htmlFor }) {
  return (
    <div className={clsx('space-y-1.5', className)}>
      {label && (
        <label htmlFor={htmlFor} className="block text-[13px] font-medium text-ink">
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-[12px] text-bad flex items-center gap-1">
          <AlertCircle className="h-3 w-3 shrink-0" aria-hidden />
          {error}
        </p>
      ) : (
        hint && <p className="text-[12px] text-muted">{hint}</p>
      )}
    </div>
  );
}

export function Input({ className, ...props }) {
  return <input className={clsx(FIELD_BASE, 'h-10', className)} {...props} />;
}

export function Textarea({ className, ...props }) {
  return <textarea className={clsx(FIELD_BASE, 'py-2.5 min-h-[120px] resize-y leading-relaxed', className)} {...props} />;
}

export function Select({ className, children, ...props }) {
  return (
    <div className="relative">
      <select
        className={clsx(FIELD_BASE, 'h-10 appearance-none pr-9 cursor-pointer', className)}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
        aria-hidden
      />
    </div>
  );
}

export function Checkbox({ label, className, id, ...props }) {
  return (
    <label htmlFor={id} className={clsx('flex items-center gap-2.5 cursor-pointer select-none', className)}>
      <input id={id} type="checkbox" className="peer sr-only" {...props} />
      <span
        className={clsx(
          'h-[18px] w-[18px] shrink-0 rounded border border-line bg-surface grid place-items-center',
          'transition-colors peer-checked:bg-brand peer-checked:border-brand',
          'peer-focus-visible:ring-2 peer-focus-visible:ring-brand-accent peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-canvas',
        )}
      >
        <Check className="h-3 w-3 text-brand-ink opacity-0 peer-checked:opacity-100" aria-hidden />
      </span>
      <span className="text-sm text-ink">{label}</span>
    </label>
  );
}

/* --------------------------------------------------------------------------- */
/* Feedback                                                                     */
/* --------------------------------------------------------------------------- */

export function Spinner({ className }) {
  return <Loader2 className={clsx('h-5 w-5 animate-spin text-brand', className)} aria-hidden />;
}

export function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <div className={clsx('flex flex-col items-center justify-center py-14 px-6 text-center', className)}>
      {Icon && (
        <div className="mb-4 grid h-12 w-12 place-items-center rounded-full bg-raised">
          <Icon className="h-6 w-6 text-faint" aria-hidden />
        </div>
      )}
      <p className="text-[15px] font-medium text-ink">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorNote({ children, onRetry, retryLabel = 'Try again', className }) {
  if (!children) return null;
  return (
    <div
      role="alert"
      className={clsx('flex items-start gap-2.5 rounded border border-bad/25 bg-bad-soft px-3.5 py-3', className)}
    >
      <AlertCircle className="h-4 w-4 shrink-0 text-bad mt-0.5" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] text-bad leading-relaxed">{children}</p>
        {onRetry && (
          <button onClick={onRetry} className="mt-1.5 text-[13px] font-semibold text-bad underline">
            {retryLabel}
          </button>
        )}
      </div>
    </div>
  );
}

export function Skeleton({ className }) {
  return <div className={clsx('skeleton', className)} />;
}

/* --------------------------------------------------------------------------- */
/* Score ring                                                                   */
/* --------------------------------------------------------------------------- */

export function ScoreRing({ score = 0, size = 104, label }) {
  const stroke = size >= 90 ? 8 : 6;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const tone = clamped >= 85 ? 'var(--ok)' : clamped >= 60 ? 'var(--warn)' : 'var(--bad)';

  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${label || 'Score'}: ${clamped} out of 100`}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke}
          stroke="rgb(var(--line))"
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke}
          stroke={`rgb(${tone})`} strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (clamped / 100) * circumference}
          style={{ transition: 'stroke-dashoffset 700ms cubic-bezier(0.16, 1, 0.3, 1)' }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <span
          className="tnum font-semibold leading-none text-ink"
          style={{ fontSize: size * 0.28 }}
        >
          {clamped}
        </span>
        {label && size >= 90 && (
          <span className="absolute bottom-[18%] text-[10px] uppercase tracking-wide text-faint">
            {label}
          </span>
        )}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------- */
/* Modal                                                                        */
/* --------------------------------------------------------------------------- */

export function Modal({ open, onClose, title, children, footer, size = 'md' }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    document.addEventListener('keydown', onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    ref.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div
        className="absolute inset-0 bg-ink/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden
      />
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx(
          'relative w-full bg-surface shadow-pop animate-fade-up outline-none',
          'rounded-t-xl sm:rounded-xl max-h-[92vh] flex flex-col',
          size === 'lg' ? 'sm:max-w-3xl' : size === 'sm' ? 'sm:max-w-md' : 'sm:max-w-xl',
        )}
      >
        <div className="flex items-center justify-between gap-4 px-5 py-4 border-b border-line shrink-0">
          <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
          <button
            onClick={onClose}
            className="rounded p-1.5 text-muted hover:bg-raised hover:text-ink transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <div className="overflow-y-auto p-5 flex-1">{children}</div>
        {footer && <div className="border-t border-line px-5 py-4 shrink-0">{footer}</div>}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------------------- */
/* Stat tile                                                                    */
/* --------------------------------------------------------------------------- */

export function Stat({ label, value, sub, tone = 'neutral', icon: Icon }) {
  const valueTone = {
    neutral: 'text-ink',
    ok: 'text-ok',
    warn: 'text-warn',
    bad: 'text-bad',
    brand: 'text-brand',
  }[tone];

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[13px] font-medium text-muted">{label}</p>
        {Icon && <Icon className="h-4 w-4 text-faint shrink-0" aria-hidden />}
      </div>
      <p className={clsx('mt-2 tnum text-[28px] font-semibold leading-none', valueTone)}>{value}</p>
      {sub && <p className="mt-1.5 text-[12px] text-faint">{sub}</p>}
    </Card>
  );
}
