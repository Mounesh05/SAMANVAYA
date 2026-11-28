import React from 'react';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';

const types = ['number', 'string', 'boolean', 'null', 'array', 'object'];
const blankValue = () => ({ type: 'number', text: '' });
const blankCase = () => ({ id: '', args: [], expected: blankValue() });
export const newFixtureForm = () => ({ name: '', version: '1', mutation: 'forbidden', cases: [blankCase()] });

function readValue({ type, text }, label) {
  if (type === 'string') return text;
  if (type === 'null') return null;
  if (type === 'boolean') return text === 'true';
  if (type === 'number' && text.trim() && Number.isFinite(Number(text))) return Number(text);
  if (type === 'array' || type === 'object') {
    try {
      const value = JSON.parse(text);
      if (value !== null && typeof value === 'object' && Array.isArray(value) === (type === 'array')) return value;
    } catch { /* Show the field name in the validation error. */ }
  }
  throw Error(`Enter a valid ${type} for ${label}.`);
}

export function fixturePayload(form) {
  const datasets = form.cases.map(c => ({
    id: c.id.trim(), args: c.args.map((arg, i) => readValue(arg, `${c.id} argument ${i + 1}`)),
    expected: readValue(c.expected, `${c.id} expected result`),
  }));
  if (!form.name.trim() || !form.version.trim() || datasets.some(d => !d.id)) throw Error('Enter a contract name, version and name for each case.');
  if (new Set(datasets.map(d => d.id)).size !== datasets.length) throw Error('Give each case a distinct name.');
  return {
    contract: { kind: 'function', name: form.name.trim(), version: form.version.trim(), mutation: form.mutation,
      input_schema: { type: 'array' }, output_schema: {}, correctness: 'expected', output: { source: 'return' } },
    datasets,
  };
}

function ValueField({ label, value, onChange }) {
  return <div className="ai-fields">
    <Select label={label + ' type'} value={value.type} placeholder={null} options={types}
      onChange={e => onChange({ type: e.target.value, text: e.target.value === 'boolean' ? 'false' : '' })} />
    {value.type === 'boolean' ? <Select label={label} placeholder={null} value={value.text} options={['false', 'true']}
      onChange={e => onChange({ ...value, text: e.target.value })} /> : value.type !== 'null' &&
      <Input label={label} value={value.text} type={value.type === 'number' ? 'number' : 'text'}
        helperText={['object', 'array'].includes(value.type) ? 'Enter this structured value in JSON.' : undefined}
        onChange={e => onChange({ ...value, text: e.target.value })} />}
  </div>;
}

export function FunctionFixtures({ value, onChange }) {
  const updateCase = (index, patch) => onChange({ ...value, cases: value.cases.map((item, i) => i === index ? { ...item, ...patch } : item) });
  return <section className="ai-stack" aria-label="Function contract and validation cases">
    <div className="ai-fields">
      <Input label="Contract name" value={value.name} maxLength={128} onChange={e => onChange({ ...value, name: e.target.value })} />
      <Input label="Contract version" value={value.version} maxLength={64} onChange={e => onChange({ ...value, version: e.target.value })} />
      <Select label="Input mutation" placeholder={null} value={value.mutation} options={['forbidden', 'allowed']}
        onChange={e => onChange({ ...value, mutation: e.target.value })} />
    </div>
    {value.cases.map((item, i) => <fieldset className="ai-review" key={i}>
      <legend>Validation case {i + 1}</legend>
      <Input label="Case name" maxLength={128} value={item.id} onChange={e => updateCase(i, { id: e.target.value })} />
      {item.args.map((arg, j) => <div key={j} className="ai-stack">
        <ValueField label={`Argument ${j + 1}`} value={arg} onChange={next => updateCase(i, { args: item.args.map((v, n) => n === j ? next : v) })} />
        <Button type="button" size="sm" variant="ghost" onClick={() => updateCase(i, { args: item.args.filter((_, n) => n !== j) })}>Remove argument {j + 1}</Button>
      </div>)}
      <Button type="button" size="sm" variant="outline" disabled={item.args.length >= 32} onClick={() => updateCase(i, { args: [...item.args, blankValue()] })}>Add argument</Button>
      <ValueField label="Expected return value" value={item.expected} onChange={expected => updateCase(i, { expected })} />
      {value.cases.length > 1 && <Button type="button" size="sm" variant="ghost" onClick={() => onChange({ ...value, cases: value.cases.filter((_, j) => j !== i) })}>Remove case</Button>}
    </fieldset>)}
    <Button type="button" size="sm" variant="outline" disabled={value.cases.length >= 32} onClick={() => onChange({ ...value, cases: [...value.cases, blankCase()] })}>Add validation case</Button>
  </section>;
}
