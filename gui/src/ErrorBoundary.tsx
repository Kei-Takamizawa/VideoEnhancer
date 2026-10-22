import { CopyMessage } from "./Notice";
import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { ActionButton } from "./ActionButton";

export class ErrorBoundary extends Component<
  { children: ReactNode; scope: string }, { details: string }
> {
  state = { details: "" };
  static getDerivedStateFromError(error: Error) {
    return { details: error.stack || error.message || String(error) };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    const details = `${this.props.scope}\n${error.stack || error.message}\n${info.componentStack}`;
    this.setState({ details });
    console.error(details);
    void window.desktop.logRendererError?.(details).catch(() => {});
  }
  render() {
    return this.state.details ? <div className="error card" role="alert">
      <h2>Something went wrong on this screen</h2>
      <CopyMessage text={this.state.details} /><p>Reload to try again. Your saved videos and settings are kept.</p>
      <ActionButton onClick={() => void window.desktop.reload?.()}>Reload</ActionButton>
      <ActionButton onClick={() => window.desktop.copy(this.state.details)}>Copy details</ActionButton>
    </div> : this.props.children;
  }
}
