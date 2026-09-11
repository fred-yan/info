import { Component, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NavBar from './components/NavBar';
import { MultiPlatformPage } from './pages/MultiPlatformPage';
import { HotspotPage } from './pages/HotspotPage';
import PlatformStatus from './components/PlatformStatus';
import { SettingsContext } from './contexts/SettingsContext';
import { useSettings } from './hooks/useSettings';

interface ErrorBoundaryProps  { children: ReactNode; }
interface ErrorBoundaryState  { hasError: boolean; error: Error | null; }

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  handleReset = () => this.setState({ hasError: false, error: null });

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-fallback" role="alert">
          <h1>应用出现错误</h1>
          <p>{this.state.error?.message || '未知错误'}</p>
          <button type="button" onClick={this.handleReset}>重试</button>
        </div>
      );
    }
    return this.props.children;
  }
}

function AppInner() {
  const settings = useSettings();

  return (
    <SettingsContext.Provider value={settings}>
      <BrowserRouter>
        <NavBar />
        <main style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Routes>
            <Route path="/"          element={<MultiPlatformPage />} />
            <Route path="/keywords"  element={<HotspotPage />} />
            <Route path="/platforms" element={<PlatformStatus />} />
          </Routes>
        </main>
      </BrowserRouter>
    </SettingsContext.Provider>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <AppInner />
    </ErrorBoundary>
  );
}

export default App;
