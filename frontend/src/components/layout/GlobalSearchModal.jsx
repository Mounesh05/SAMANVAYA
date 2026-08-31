import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FolderGit2, ListTodo, Users, ShieldCheck, ArrowRight, X } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { ROLES } from '../../utils/constants';

export function GlobalSearchModal({ isOpen, onClose, onOpen }) {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        isOpen ? onClose() : onOpen?.();
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, onOpen]);

  if (!isOpen) return null;

  // Search items list based on permissions
  const searchItems = [
    { title: 'Projects Portfolio', category: 'Projects', to: '/projects', icon: <FolderGit2 size={16} /> },
    { title: 'Active Sprints', category: 'Sprints', to: '/sprints', icon: <FolderGit2 size={16} /> },
    { title: 'Tasks & Backlog', category: 'Work', to: '/tasks', icon: <ListTodo size={16} /> },
    { title: 'Interactive Kanban Board', category: 'Work', to: '/board', icon: <ListTodo size={16} /> },
    { title: 'Code Quality Analysis', category: 'Intelligence', to: '/code-quality', icon: <ShieldCheck size={16} /> },
    { title: 'GitHub PR Synchronizer', category: 'Engineering', to: '/github/sync', icon: <ShieldCheck size={16} /> },
    { title: 'CI/CD Log Analyzer AI', category: 'Engineering', to: '/cicd-logs', icon: <ShieldCheck size={16} /> },
    { title: 'Performance Dashboard', category: 'Performance', to: '/performance', icon: <ShieldCheck size={16} /> },
    { title: 'Reports & Analytics', category: 'Reports', to: '/reports', icon: <FolderGit2 size={16} /> },
    ...(role === ROLES.HR || role === ROLES.CEO
      ? [
          { title: 'Employees Directory', category: 'People', to: '/employees', icon: <Users size={16} /> },
          { title: 'Teams Management', category: 'People', to: '/teams', icon: <Users size={16} /> },
        ]
      : []),
  ];

  const filtered = query
    ? searchItems.filter(
        (item) =>
          item.title.toLowerCase().includes(query.toLowerCase()) ||
          item.category.toLowerCase().includes(query.toLowerCase())
      )
    : searchItems;

  const handleSelect = (to) => {
    onClose();
    navigate(to);
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 999,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '10vh',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '560px',
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-xl)',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '1rem 1.25rem',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <Search size={18} style={{ color: 'var(--text-muted)' }} />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search projects, tasks, employees, code quality..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '1rem',
              outline: 'none',
            }}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Results */}
        <div style={{ maxHeight: '360px', overflowY: 'auto', padding: '0.75rem' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              No matching pages or entities found for "{query}"
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              {filtered.map((item) => (
                <div
                  key={item.title}
                  onClick={() => handleSelect(item.to)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.65rem 0.85rem',
                    borderRadius: 'var(--radius-md)',
                    cursor: 'pointer',
                    transition: 'background var(--transition-fast)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-elevated)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{ color: 'var(--primary)' }}>{item.icon}</div>
                    <div>
                      <div style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-primary)' }}>
                        {item.title}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {item.category}
                      </div>
                    </div>
                  </div>
                  <ArrowRight size={14} style={{ color: 'var(--text-muted)' }} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
