import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AssignedFeedbackPage } from './AssignedFeedbackPage';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Select } from '../../components/common/Select';
import { employeesApi } from '../../api/employees.api';
import { feedbackApi } from '../../api/feedback.api';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { useAuthStore } from '../../store/useAuthStore';
import { useSessionScope } from '../../store/useSessionScope';
import { canOpenPage } from '../../routes/access';

export function FeedbackPage() {
  const user = useAuthStore((state) => state.user);
  const sessionScope = useSessionScope();
  return <div className="scoring-stack">
    <AssignedFeedbackPage />
    {canOpenPage(user, 'performance') && <p><Link to="/performance/assessments">View assessment history</Link></p>}
    {user?.role === 'HR' && hasPermission(user, PERMISSIONS.VIEW_HR_PERFORMANCE_ASSESSMENT) &&
      <HistoricalHRCases key={sessionScope} sessionScope={sessionScope} reviewer={user.employee_id} />}
  </div>;
}

const historicalSubjectRoles = new Set(['DEVELOPER', 'LEAD', 'QA', 'DEVOPS']);

function HistoricalHRCases({ sessionScope, reviewer }) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState('');
  const employees = useQuery({ queryKey: ['hr-case-subjects', sessionScope], queryFn: () => employeesApi.list(), enabled: open });
  const subjects = (employees.data || []).filter((employee) =>
    employee.employee_id !== reviewer && historicalSubjectRoles.has(employee.role?.toUpperCase()));
  const hasSubject = subjects.some((subject) => subject.employee_id === selected);
  const record = useQuery({ queryKey: ['historical-hr-case', sessionScope, selected],
    queryFn: () => feedbackApi.getHRAssessment(selected), enabled: open && hasSubject, retry: false, gcTime: 0 });
  return <Card title="Historical workplace assessments" subtitle="Read the historical cases you authored, including saved drafts.">
    <Button variant="secondary" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Close case history' : 'Open case history'}</Button>
    {open && <div className="scoring-stack">
      {employees.isPending ? <p role="status">Loading employees…</p> : employees.isError ?
        <div role="alert"><p>Employees could not be loaded.</p><Button onClick={() => employees.refetch()}>Retry employee list</Button></div> :
        !subjects.length ? <p>No eligible employees in your scope.</p> :
        <Select label="Historical case employee" value={selected} onChange={(event) => setSelected(event.target.value)}
          options={subjects.map((subject) => ({ value: subject.employee_id, label: `${subject.name} · ${subject.employee_id}` }))} />}
      {hasSubject && (record.isPending ? <p role="status">Loading case history…</p> : record.isError ?
        <div role="alert"><p>This case could not be loaded for your account.</p><Button onClick={() => record.refetch()}>Retry case history</Button></div> :
        record.data ? <div className="scoring-stack">
          <h3>Historical {record.data.status || 'assessment'}</h3>
          {record.data.general_comments && <p>{record.data.general_comments}</p>}
          {Object.entries(record.data.dimensions || {}).map(([key, item]) => <section key={key}>
            <h4>{key.replaceAll('_', ' ')}</h4>
            <p>{item.is_not_observed ? 'Not observed' : item.rating == null ? 'Rating unavailable' : `Historical rating · ${item.rating}/4`}</p>
            {item.compliance_status && <p>Compliance · {item.compliance_status.replaceAll('_', ' ')}</p>}
            {item.evidence_description && <p>{item.evidence_description}</p>}
            {item.evidence_reference && <p>{item.evidence_reference}</p>}
            {item.comments && <p>{item.comments}</p>}
          </section>)}
        </div> : <p>No historical case authored by you was found for this employee.</p>)}
    </div>}
  </Card>;
}
