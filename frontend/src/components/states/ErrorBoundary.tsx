import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Catches render-time exceptions below it and shows a recoverable panel.
 *
 * React unmounts the entire tree when a render throws, so without a boundary
 * any single component error blanks the whole application -- header, nav and
 * all -- with nothing on screen and nothing in the UI to act on. That is the
 * worst possible failure mode during a live demonstration: no message, no
 * route, no way back except knowing to reload.
 *
 * This has to be a class component. Error boundaries are the one React
 * feature with no hook equivalent -- there is no `useErrorBoundary`.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Kept as console output rather than shipped anywhere: this is a
    // single-instance research tool with no error-reporting backend, and
    // inventing one would be over-engineering. The stack still reaches
    // devtools, which is where it is useful.
    console.error("Unhandled render error:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div
        role="alert"
        className="border border-line bg-surface rounded-[3px] px-4 py-5"
      >
        <h2 className="text-sm font-semibold text-ink">Something went wrong on this page</h2>
        <p className="mt-2 text-sm text-muted">
          The rest of the application is still working — you can go back, or reload to try again.
        </p>
        <p className="mt-3 font-mono text-[11px] break-words text-subtle">
          {this.state.error.message}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="rounded-[3px] bg-accent px-3 py-2 text-xs font-medium text-accent-ink"
          >
            Try again
          </button>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-[3px] border border-line-strong px-3 py-2 text-xs font-medium text-ink"
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}
