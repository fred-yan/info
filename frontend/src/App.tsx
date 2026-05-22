import { Component, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NavBar from './components/NavBar';
import { HotspotPage } from './pages/HotspotPage';
import { NewsFeedPage } from './pages/NewsFeedPage';
import PlatformStatus from './components/PlatformStatus';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-fallback" role="alert">
          <h1>应用出现错误</h1>
          <p>{this.state.error?.message || '未知错误'}</p>
          <button type="button" onClick={this.handleReset}>
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <NavBar />
        <Routes>
          <Route path="/" element={<HotspotPage />} />
          <Route path="/feed" element={<NewsFeedPage />} />
          <Route path="/platforms" element={<PlatformStatus />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
