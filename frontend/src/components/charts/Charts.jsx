/*
 * Small dashboard charts drawn with HTML and CSS (no chart library).
 *
 * Every chart shows only the numbers it is given, prints its values (legend,
 * bar tips or a hidden table) so colour never carries meaning alone, and has
 * a hover/focus tooltip. Colours come from the --viz-* tokens in index.css,
 * which have a dark and a light set.
 */
import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, CircleAlert } from 'lucide-react';
import { formatNumber, share, toneOf } from './chartData';
import './Charts.css';


/* ── Tooltip ─────────────────────────────────────────────────── */

function useTooltip() {
  const [tip, setTip] = useState(null);

  const show = (event, content) => {
    const box = event.currentTarget.closest('.viz')?.getBoundingClientRect();
    if (!box) return;
    const target = event.currentTarget.getBoundingClientRect();
    const pointer = event.clientX != null && event.type.startsWith('mouse');
    const x = (pointer ? event.clientX : target.left + target.width / 2) - box.left;
    const y = (pointer ? event.clientY : target.top) - box.top;
    setTip({ x: Math.min(Math.max(x, 70), Math.max(box.width - 70, 70)), y, content });
  };
  const hide = () => setTip(null);
  const bind = (content) => ({
    onMouseMove: (event) => show(event, content),
    onMouseLeave: hide,
    onFocus: (event) => show(event, content),
    onBlur: hide,
  });

  const node = tip ? (
    <div className="viz-tip" style={{ left: tip.x, top: tip.y }} role="presentation">
      {tip.content.title && <div className="viz-tip-title">{tip.content.title}</div>}
      {tip.content.rows.map((row) => (
        <div className="viz-tip-row" key={row.label}>
          {row.tone && <span className="viz-key" style={{ background: toneOf(row.tone).fill }} />}
          <span className="viz-tip-label">{row.label}</span>
          <span className="viz-tip-value">{row.value}</span>
        </div>
      ))}
    </div>
  ) : null;

  return { bind, node };
}

export function ChartEmpty({ children = 'No data yet.' }) {
  return <p className="viz-empty">{children}</p>;
}

export function Legend({ items }) {
  return (
    <ul className="viz-legend">
      {items.map((item) => (
        <li key={item.label}>
          <span className="viz-key" style={{ background: toneOf(item.tone).fill }} />
          <span className="viz-legend-label">{item.label}</span>
          {item.value != null && <span className="viz-legend-value">{item.value}</span>}
        </li>
      ))}
    </ul>
  );
}

/* ── Segmented bar: one whole split into parts ──────────────── */

export function SegmentedBar({ label, parts, emptyText, format = formatNumber }) {
  const tooltip = useTooltip();
  const total = parts.reduce((sum, part) => sum + (part.value || 0), 0);
  if (!total) return <ChartEmpty>{emptyText}</ChartEmpty>;

  const describe = parts.map((part) => `${part.label} ${format(part.value || 0)} (${share(part.value || 0, total)}%)`).join(', ');

  return (
    <div className="viz">
      <div className="viz-seg" role="img" aria-label={`${label}: ${describe}`}>
        {parts.filter((part) => part.value > 0).map((part) => {
          const pct = share(part.value, total);
          const tone = toneOf(part.tone);
          return (
            <div
              key={part.label}
              className="viz-seg-part"
              tabIndex={0}
              aria-label={`${part.label}: ${format(part.value)} (${pct}%)`}
              style={{ flexGrow: part.value, background: tone.fill, color: tone.ink }}
              {...tooltip.bind({ title: part.label, rows: [
                { label: 'Count', value: format(part.value) },
                { label: 'Share', value: `${pct}%` },
              ] })}
            >
              {pct >= 12 && <span>{pct}%</span>}
            </div>
          );
        })}
      </div>
      <Legend items={parts.map((part) => ({ label: part.label, tone: part.tone, value: format(part.value || 0) }))} />
      {tooltip.node}
    </div>
  );
}

/* ── Bar list: one measure across named items ───────────────── */

export function BarList({ label, items, emptyText, format = formatNumber, limit = 8, tone = 'blue', onSelect }) {
  const tooltip = useTooltip();
  const rows = [...items].filter((item) => item.value > 0).sort((a, b) => b.value - a.value);
  if (!rows.length) return <ChartEmpty>{emptyText}</ChartEmpty>;

  const shown = rows.slice(0, limit);
  const rest = rows.slice(limit);
  if (rest.length) {
    shown.push({ key: '__other', label: `Other (${rest.length})`, value: rest.reduce((sum, item) => sum + item.value, 0), other: true });
  }
  const max = Math.max(...shown.map((item) => item.value));

  return (
    <div className="viz">
      <ul className="viz-bars" aria-label={label}>
        {shown.map((item) => {
          const fill = toneOf(item.other ? 'neutral' : item.tone || tone).fill;
          const clickable = onSelect && !item.other;
          const Track = clickable ? 'button' : 'span';
          return (
            <li key={item.key || item.label}>
              <span className="viz-bars-label" title={item.label}>{item.label}</span>
              <Track
                className={`viz-bars-track${clickable ? ' is-clickable' : ''}`}
                tabIndex={0}
                type={clickable ? 'button' : undefined}
                aria-label={`${item.label}: ${format(item.value)}${item.note ? `, ${item.note}` : ''}`}
                onClick={clickable ? () => onSelect(item) : undefined}
                {...tooltip.bind({ title: item.label, rows: [
                  { label: label, value: format(item.value) },
                  ...(item.note ? [{ label: 'Note', value: item.note }] : []),
                ] })}
              >
                <span className="viz-bars-bar" style={{ width: `${Math.max((item.value / max) * 100, 1.5)}%`, background: fill }} />
                <span className="viz-bars-value">{format(item.value)}</span>
              </Track>
            </li>
          );
        })}
      </ul>
      {tooltip.node}
    </div>
  );
}

/* ── Meter: a percentage against a goal direction ───────────── */

const METER_STATES = {
  good: { label: 'On track', Icon: CheckCircle2 },
  warning: { label: 'Needs attention', Icon: CircleAlert },
  critical: { label: 'At risk', Icon: AlertTriangle },
};

export function Meter({ label, value, caption, emptyText, thresholds = [50, 75] }) {
  if (value == null || Number.isNaN(Number(value))) return <ChartEmpty>{emptyText}</ChartEmpty>;
  const pct = Math.max(0, Math.min(100, Number(value)));
  const state = pct >= thresholds[1] ? 'good' : pct >= thresholds[0] ? 'warning' : 'critical';
  const { label: stateLabel, Icon } = METER_STATES[state];
  const tone = toneOf(state);

  return (
    <div className="viz-meter">
      <div className="viz-meter-head">
        <span className="viz-meter-value">{Math.round(pct * 10) / 10}%</span>
        <span className={`viz-state viz-state--${state}`}>
          <Icon size={14} aria-hidden="true" /> {stateLabel}
        </span>
      </div>
      <div
        className="viz-meter-track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        style={{ background: `color-mix(in srgb, ${tone.fill} 18%, transparent)` }}
      >
        <span style={{ width: `${pct}%`, background: tone.fill }} />
      </div>
      {caption && <p className="viz-caption">{caption}</p>}
    </div>
  );
}

/* ── Stacked columns over time ──────────────────────────────── */

function niceMax(value) {
  if (value <= 4) return Math.max(value, 1);
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => value <= s * power) * power;
  return step;
}

export function StackedColumns({ label, data, series, emptyText, height = 180, onSelect }) {
  const tooltip = useTooltip();
  const totals = data.map((point) => series.reduce((sum, s) => sum + (point.values[s.key] || 0), 0));
  if (!data.length || !totals.some(Boolean)) return <ChartEmpty>{emptyText}</ChartEmpty>;

  const top = niceMax(Math.max(...totals));
  const ticks = [0, top / 2, top].map((tick) => Math.round(tick * 10) / 10);
  const labelEvery = Math.ceil(data.length / 7);

  return (
    <div className="viz">
      {series.length > 1 && <Legend items={series.map((s) => ({ label: s.label, tone: s.tone }))} />}
      <div className="viz-cols" role={onSelect ? 'group' : 'img'} aria-label={`${label}, ${data.length} days`}>
        <div className="viz-cols-axis" style={{ height }}>
          {[...ticks].reverse().map((tick) => <span key={tick}>{formatNumber(tick)}</span>)}
        </div>
        <div className="viz-cols-body">
          <div className="viz-cols-plot" style={{ height }}>
            {ticks.map((tick) => (
              <span key={tick} className="viz-cols-grid" style={{ bottom: `${(tick / top) * 100}%` }} />
            ))}
            {data.map((point, index) => {
              const parts = series.filter((s) => point.values[s.key] > 0);
              return (
                <div
                  key={point.key}
                  className="viz-cols-slot"
                  tabIndex={0}
                  role={onSelect ? 'button' : undefined}
                  onClick={onSelect ? () => onSelect(point) : undefined}
                  onKeyDown={onSelect ? (event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onSelect(point);
                    }
                  } : undefined}
                  aria-label={`${point.label}: ${series.map((s) => `${s.label} ${point.values[s.key] || 0}`).join(', ')}`}
                  {...tooltip.bind({ title: point.label, rows: series.map((s) => ({ label: s.label, tone: s.tone, value: formatNumber(point.values[s.key] || 0) })) })}
                >
                  <div className="viz-cols-stack" style={{ height: `${(totals[index] / top) * 100}%` }}>
                    {parts.map((s) => (
                      <span key={s.key} style={{ flexGrow: point.values[s.key], background: toneOf(s.tone).fill }} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="viz-cols-x">
            {data.map((point, index) => (
              <span key={point.key}>{index % labelEvery === 0 || index === data.length - 1 ? point.short : ''}</span>
            ))}
          </div>
        </div>
      </div>
      <div className="viz-sr-only">
        <table>
          <caption>{label}</caption>
          <thead><tr><th>Date</th>{series.map((s) => <th key={s.key}>{s.label}</th>)}</tr></thead>
          <tbody>
            {data.map((point) => (
              <tr key={point.key}><td>{point.label}</td>{series.map((s) => <td key={s.key}>{point.values[s.key] || 0}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {tooltip.node}
    </div>
  );
}

/* ── Timeline: date ranges against today ────────────────────── */

const parseDay = (value) => {
  if (!value) return null;
  const date = new Date(String(value).length <= 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(date.getTime()) ? null : date;
};

export function Timeline({ label, items, emptyText, today = new Date(), limit = 8, onSelect }) {
  const tooltip = useTooltip();
  const rows = items
    .map((item) => ({ ...item, from: parseDay(item.start), to: parseDay(item.end) }))
    .filter((item) => item.from && item.to && item.to >= item.from)
    .sort((a, b) => a.to - b.to)
    .slice(0, limit);
  if (!rows.length) return <ChartEmpty>{emptyText}</ChartEmpty>;

  const min = Math.min(...rows.map((row) => row.from.getTime()));
  const max = Math.max(...rows.map((row) => row.to.getTime()));
  const span = Math.max(max - min, 86400000);
  const at = (time) => ((time - min) / span) * 100;
  const todayPct = today.getTime() >= min && today.getTime() <= max ? at(today.getTime()) : null;
  const fmt = (date) => date.toLocaleDateString('en', { day: 'numeric', month: 'short', year: 'numeric' });

  return (
    <div className="viz">
      {todayPct != null && (
        <div className="viz-timeline-axis viz-timeline-head" aria-hidden="true">
          <span />
          <span className="viz-timeline-axis-dates">
            <span className="viz-timeline-axis-today" style={{ left: `${todayPct}%` }}>Today</span>
          </span>
          <span />
        </div>
      )}
      <ul className="viz-timeline" aria-label={label}>
        {rows.map((row) => {
          const late = row.open && row.to < today;
          const tone = toneOf(late ? 'critical' : row.open ? 'blue' : 'neutral');
          return (
            <li key={row.key}>
              <span className="viz-bars-label" title={row.label}>{row.label}</span>
              <span
                className={`viz-timeline-track${onSelect ? ' is-clickable' : ''}`}
                tabIndex={0}
                role={onSelect ? 'button' : undefined}
                aria-label={`${row.label}: ${fmt(row.from)} to ${fmt(row.to)}${late ? ', past target end' : ''}`}
                onClick={onSelect ? () => onSelect(row) : undefined}
                onKeyDown={onSelect ? (event) => { if (event.key === 'Enter') onSelect(row); } : undefined}
                {...tooltip.bind({ title: row.label, rows: [
                  { label: 'Start', value: fmt(row.from) },
                  { label: 'Target end', value: fmt(row.to) },
                  ...(row.status ? [{ label: 'Status', value: row.status }] : []),
                  ...(late ? [{ label: 'Note', value: 'Past target end' }] : []),
                ] })}
              >
                {todayPct != null && <span className="viz-timeline-today" style={{ left: `${todayPct}%` }} />}
                <span
                  className="viz-timeline-bar"
                  style={{ left: `${at(row.from.getTime())}%`, width: `${Math.max(at(row.to.getTime()) - at(row.from.getTime()), 1.5)}%`, background: tone.fill }}
                />
              </span>
              {late ? <span className="viz-state viz-state--critical viz-timeline-flag"><AlertTriangle size={12} aria-hidden="true" /> Late</span> : <span />}
            </li>
          );
        })}
      </ul>
      <div className="viz-timeline-axis" aria-hidden="true">
        <span />
        <span className="viz-timeline-axis-dates">
          <span>{fmt(new Date(min))}</span>
          <span>{fmt(new Date(max))}</span>
        </span>
        <span />
      </div>
      {tooltip.node}
    </div>
  );
}
