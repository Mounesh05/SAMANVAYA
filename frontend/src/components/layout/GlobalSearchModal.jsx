import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FolderGit2, ListTodo, Users, ShieldCheck, ArrowRight, X } from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { canOpenPage } from '../../routes/access';

export function GlobalSearchModal({ isOpen, onClose, onOpen }) {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();
  const { user } = useAuthStore();

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
        else onOpen?.();
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, onOpen]);

  if (!isOpen) return null;

  // Each entry names its page in the shared access table (routes/access.js),
  // so search never offers a page the router would refuse.
  const searchItems = [
    { page: 'projects', title: 'Projects Portfolio', category: 'Projects', to: '/projects', icon: <FolderGit2 size={16} /> },
    { page: 'sprints', title: 'Active Sprints', category: 'Sprints', to: '/sprints', icon: <FolderGit2 size={16} /> },
    { page: 'tasks', title: 'Tasks & Backlog', category: 'Work', to: '/tasks', icon: <ListTodo size={16} /> },
    { page: 'board', title: 'Interactive Kanban Board', category: 'Work', to: '/board', icon: <ListTodo size={16} /> },
    { page: 'codeQuality', title: 'Code Quality Analysis', category: 'Intelligence', to: '/code-quality', icon: <ShieldCheck size={16} /> },
    { page: 'githubSync', title: 'GitHub PR Synchronizer', category: 'Engineering', to: '/github/sync', icon: <ShieldCheck size={16} /> },
    { page: 'cicdLogs', title: 'CI/CD Log Analyzer AI', category: 'Engineering', to: '/cicd-logs', icon: <ShieldCheck size={16} /> },
    { page: 'performance', title: 'Performance Dashboard', category: 'Performance', to: '/performance', icon: <ShieldCheck size={16} /> },
    { page: 'reports', title: 'Reports & Analytics', category: 'Reports', to: '/reports', icon: <FolderGit2 size={16} /> },
    { page: 'employees', title: 'Employees Directory', category: 'People', to: '/employees', icon: <Users size={16} /> },
    { page: 'teams', title: 'Teams Management', category: 'People', to: '/teams', icon: <Users size={16} /> },
  ].filter((item) => canOpenPage(user, item.page));

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
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '10vh',
        paddingInline: 16,
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
          <Search size={16} strokeWidth={1.5} aria-hidden="true" style={{ color: 'var(--text-muted)' }} />
          <input
            autoFocus
            type="text"
            aria-label="Search pages"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages"
            style={{
              flex: 1,
              minWidth: 0,
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '1rem',
            }}
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
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
              No pages match “{query}”
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {filtered.map((item) => (
                <button
                  type="button"
                  className="search-result"
                  key={item.title}
                  onClick={() => handleSelect(item.to)}
                >
                  <span className="search-result-main">
                    <span className="search-result-icon" aria-hidden="true">{item.icon}</span>
                    <span>
                      <strong>
                        {item.title}
                      </strong>
                      <small>{item.category}</small>
                    </span>
                  </span>
                  <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
