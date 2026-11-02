import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { NAVIGATION } from '../data/navigation';
import * as Icons from 'lucide-react';
import { LogOut } from 'lucide-react';

export default function Sidebar() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const role = user?.role || '';
    const navItems = NAVIGATION[role] || [];

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const getIcon = (iconName) => {
        const Icon = Icons[iconName];
        return Icon ? <Icon size={20} className="nav-icon" /> : null;
    };

    return (
        <aside className="sidebar">
            {/* Brand */}
            <div className="sidebar-brand" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <img
                    src="/logo.jpeg"
                    alt="Samanvaya"
                    style={{
                        width: 44,
                        height: 44,
                        borderRadius: 10,
                        objectFit: 'cover',
                        boxShadow: '0 0 16px rgba(99, 102, 241, 0.5)',
                        border: '1.5px solid rgba(255, 255, 255, 0.25)',
                        flexShrink: 0
                    }}
                />
                <span className="sidebar-brand-name">Samanvaya</span>
            </div>

            {/* Navigation */}
            <nav className="sidebar-nav">
                {navItems.map((item, i) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                            `sidebar-nav-item ${isActive ? 'active' : ''}`
                        }
                        style={{ animationDelay: `${i * 0.04}s` }}
                    >
                        {getIcon(item.icon)}
                        <span>{item.label}</span>
                    </NavLink>
                ))}
            </nav>

            {/* Logout Button */}
            <div className="sidebar-logout">
                <button className="sidebar-logout-btn" onClick={handleLogout}>
                    <LogOut size={20} />
                    <span>Logout</span>
                </button>
            </div>
        </aside>
    );
}
