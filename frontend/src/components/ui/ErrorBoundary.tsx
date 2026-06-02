import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="grid h-full place-items-center bg-slate-50 p-6 dark:bg-slate-950">
          <div className="card max-w-md p-6 text-center">
            <AlertTriangle className="mx-auto h-10 w-10 text-amber-500" />
            <h1 className="mt-4 text-lg font-semibold">Something went wrong</h1>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              {this.state.error.message}
            </p>
            <button
              className="btn-primary mt-4"
              onClick={() => {
                this.setState({ error: null });
                window.location.assign("/");
              }}
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
