import React from 'react';

export function Table({
  columns = [], // [ { key, header, render, width, align } ]
  data = [],
  keyExtractor = (item, idx) => item.id || item.employee_id || item.run_id || idx,
  onRowClick = null,
  emptyMessage = 'No records available',
  className = '',
}) {
  return (
    <div
      style={{
        width: '100%',
        overflowX: 'auto',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-subtle)',
        background: 'var(--bg-glass-card)',
      }}
      className={`table-container ${className}`}
    >
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          textAlign: 'left',
          fontSize: '0.875rem',
        }}
      >
        <thead>
          <tr
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              borderBottom: '1px solid var(--border-subtle)',
            }}
          >
            {columns.map((col) => (
              <th
                key={col.key || col.header}
                style={{
                  padding: '0.85rem 1rem',
                  fontSize: '0.75rem',
                  fontWeight: '700',
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  width: col.width || 'auto',
                  textAlign: col.align || 'left',
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                style={{
                  padding: '2.5rem 1rem',
                  textAlign: 'center',
                  color: 'var(--text-muted)',
                  fontSize: '0.875rem',
                }}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((item, idx) => {
              const rowKey = keyExtractor(item, idx);
              return (
                <tr
                  key={rowKey}
                  onClick={() => onRowClick && onRowClick(item)}
                  style={{
                    borderBottom: '1px solid var(--border-subtle)',
                    transition: 'background var(--transition-fast)',
                    cursor: onRowClick ? 'pointer' : 'default',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  {columns.map((col) => {
                    const content = col.render ? col.render(item, idx) : item[col.key];
                    return (
                      <td
                        key={col.key || col.header}
                        style={{
                          padding: '0.85rem 1rem',
                          color: 'var(--text-primary)',
                          textAlign: col.align || 'left',
                        }}
                      >
                        {content}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
