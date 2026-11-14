/* Data helpers and colour tones for the dashboard charts (Charts.jsx). */

/* Status tones (fixed) plus the one series hue and a neutral. Text set on a
   fill uses the matching ink. */
export const TONES = {
  blue: { fill: 'var(--viz-blue)', ink: '#ffffff' },
  good: { fill: 'var(--viz-good)', ink: '#ffffff' },
  warning: { fill: 'var(--viz-warning)', ink: '#0b0b0b' },
  serious: { fill: 'var(--viz-serious)', ink: '#0b0b0b' },
  critical: { fill: 'var(--viz-critical)', ink: '#ffffff' },
  neutral: { fill: 'var(--viz-neutral)', ink: 'var(--viz-neutral-ink)' },
};

export const toneOf = (tone) => TONES[tone] || TONES.blue;

const numberFormat = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 });
export const formatNumber = (value) => (value == null || Number.isNaN(value) ? '—' : numberFormat.format(value));

export const share = (value, total) => (total ? Math.round((value / total) * 100) : 0);

export const shortDate = (iso) => {
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString('en', { day: 'numeric', month: 'short' });
};

/* Turns dated records into one point per day for the last `days` days. */
export function dailyPoints(records, { days = 14, dateOf, bucketOf, today = new Date() }) {
  const points = [];
  const index = {};
  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - offset);
    const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
    const point = { key, label: day.toLocaleDateString('en', { weekday: 'short', day: 'numeric', month: 'short' }), short: shortDate(key), values: {} };
    index[key] = point;
    points.push(point);
  }
  for (const record of records) {
    const raw = dateOf(record);
    if (!raw) continue;
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) continue;
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const bucket = bucketOf(record);
    if (index[key] && bucket) index[key].values[bucket] = (index[key].values[bucket] || 0) + 1;
  }
  return points;
}

/* Points from an API trend that has one row per date with activity. Days
   between the first and last row with no activity are filled with zeros so
   the columns keep an even time scale. */
export function trendPoints(rows, keys) {
  const byDate = Object.fromEntries(rows.filter((row) => row.date).map((row) => [row.date, row]));
  const dates = Object.keys(byDate).sort();
  if (!dates.length) return [];
  const points = [];
  const last = new Date(`${dates[dates.length - 1]}T00:00:00`);
  for (let day = new Date(`${dates[0]}T00:00:00`); day <= last && points.length < 366; day.setDate(day.getDate() + 1)) {
    const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
    const row = byDate[key] || {};
    points.push({
      key,
      label: shortDate(key),
      short: shortDate(key),
      values: Object.fromEntries(keys.map((name) => [name, row[name] || 0])),
    });
  }
  return points;
}
