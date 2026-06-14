import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  retryCount: number;
}

const MAX_RETRIES = 3;

export class WebGLErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, retryCount: 0 };

  static getDerivedStateFromError(): Partial<State> {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    const next = this.state.retryCount + 1;
    if (next < MAX_RETRIES) {
      const delay = Math.min(500 * Math.pow(2, next), 2000);
      console.warn(`[WebGL] Render failed (attempt ${next}/${MAX_RETRIES}), retrying in ${delay}ms:`, error.message);
      setTimeout(() => this.setState({ hasError: false, retryCount: next }), delay);
    } else {
      console.warn(`[WebGL] 3D rendering disabled after ${MAX_RETRIES} attempts:`, error.message, info.componentStack);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="absolute inset-0 pointer-events-none z-0"
          style={{
            background: 'radial-gradient(ellipse at center, rgba(168,85,247,0.08) 0%, transparent 70%)'
          }}
        />
      );
    }
    return this.props.children;
  }
}
