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
    <div className={`table-container ${className}`}>
      <table className="work-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key || col.header}
                scope="col"
                style={{ width: col.width, textAlign: col.align }}
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
                className="work-table-empty"
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
                  className={onRowClick ? 'work-table-interactive' : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  onClick={onRowClick ? () => onRowClick(item) : undefined}
                  onKeyDown={onRowClick ? (event) => {
                    if (event.target !== event.currentTarget || !['Enter', ' '].includes(event.key)) return;
                    event.preventDefault();
                    onRowClick(item);
                  } : undefined}
                >
                  {columns.map((col) => {
                    const content = col.render ? col.render(item, idx) : item[col.key];
                    return (
                      <td
                        key={col.key || col.header}
                        style={{ textAlign: col.align }}
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
