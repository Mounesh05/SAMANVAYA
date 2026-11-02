import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import ErrorBoundary from './ErrorBoundary';
import { NAVIGATION } from '../data/navigation';
import { useAuth } from '../context/AuthContext';

export default function DashboardLayout() {
    const location = useLocation();
    const { user } = useAuth();
    const role = user?.role || '';
    const navItems = NAVIGATION[role] || [];

    /* Derive page title from current nav item */
    const currentNav = navItems.find(n => n.path === location.pathname);
    const pageTitle = currentNav?.label || 'Dashboard';

    return (
        <div className="app-layout">
            <Sidebar />
            <div className="main-area">
                <TopBar title={pageTitle} />
                <main className="page-content">
                    <div className="page-enter" key={location.pathname}>
                        <ErrorBoundary key={location.pathname + '-eb'}>
                            <Outlet />
                        </ErrorBoundary>
                    </div>
                </main>
            </div>
        </div>
    );
}
