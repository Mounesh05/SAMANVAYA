import { Component } from 'react';

export default class ErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('ErrorBoundary caught:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: 40, color: '#ef4444' }}>
                    <h2>⚠ Something went wrong</h2>
                    <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', background: '#fef2f2', padding: 16, borderRadius: 8, marginTop: 12 }}>
                        {this.state.error?.message || 'Unknown error'}
                    </pre>
                    <button onClick={() => this.setState({ hasError: false, error: null })}
                        style={{ marginTop: 12, padding: '8px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
                        Try Again
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}
