import { AlertTriangle, RotateCcw } from 'lucide-react';
import { Component } from 'react';

/**
 * Catches render errors so a bug becomes a recoverable screen instead of a blank page.
 *
 * Without one, any component that throws unmounts the whole tree and React leaves a
 * white page with nothing on it — no message, no way back. That is bad anywhere and
 * worse in the field, where an inspector has no console and no developer nearby.
 *
 * Must be a class: there is no hook equivalent of componentDidCatch.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Kept to the console rather than sent anywhere: an inspection may be on
    // screen, and error payloads are a common way to leak record contents.
    console.error('Unhandled error in the interface:', error, info?.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="grid min-h-screen place-items-center bg-canvas px-5">
        <div className="w-full max-w-md text-center">
          <div className="mx-auto mb-5 grid h-12 w-12 place-items-center rounded-full bg-bad-soft">
            <AlertTriangle className="h-6 w-6 text-bad" aria-hidden />
          </div>

          <h1 className="text-[19px] font-semibold text-ink">Something went wrong on this screen</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Your work up to the last save is safe. Reloading usually clears this.
          </p>

          <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
            <button
              onClick={() => window.location.reload()}
              className="inline-flex h-10 items-center justify-center gap-2 rounded bg-brand px-4 text-sm font-medium text-brand-ink transition-colors hover:bg-brand/90"
            >
              <RotateCcw className="h-4 w-4" aria-hidden />
              Reload
            </button>
            <button
              onClick={() => {
                window.location.href = '/';
              }}
              className="inline-flex h-10 items-center justify-center rounded border border-line bg-surface px-4 text-sm font-medium text-ink transition-colors hover:bg-raised"
            >
              Back to dashboard
            </button>
          </div>

          {/* Collapsed by default: useful when reporting a bug, noise otherwise. */}
          <details className="mt-8 text-left">
            <summary className="cursor-pointer text-[12px] text-faint">Technical detail</summary>
            <pre className="mt-2 max-h-48 overflow-auto rounded border border-line bg-raised p-3 font-mono text-[11px] leading-relaxed text-muted">
              {String(error?.stack || error?.message || error)}
            </pre>
          </details>
        </div>
      </div>
    );
  }
}
