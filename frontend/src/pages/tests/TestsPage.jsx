import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { qaApi } from '../../api/qa.api';
import { sprintsApi } from '../../api/sprints.api';
import { storiesApi } from '../../api/stories.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { SearchInput } from '../../components/common/SearchInput';
import { Badge } from '../../components/common/Badge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';

const EMPTY_CASE = {
  suite_id: '',
  story_id: '',
  task_id: '',
  title: '',
  description: '',
  objective: '',
  preconditions: '',
  expected_result: '',
  priority: 'medium',
  test_type: 'functional',
  steps_text: '',
};
const EMPTY_LIST = [];

const EMPTY_SUITE = { name: '', description: '', story_id: '' };
const EXECUTION_STATUSES = ['PASSED', 'FAILED', 'BLOCKED'];

function parseSteps(text) {
  return text.split('\n').map((line) => line.trim()).filter(Boolean).map((line, index) => {
    const [instruction, ...expected] = line.split('=>');
    return {
      step_number: index + 1,
      instruction: instruction.trim(),
      expected_result: expected.join('=>').trim(),
    };
  });
}

export function TestsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [suiteFilter, setSuiteFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [storyFilter, setStoryFilter] = useState('');
  const [search, setSearch] = useState('');
  const [modal, setModal] = useState('');
  const [storedCase, setStoredCase] = useState(null);
  const [form, setForm] = useState(EMPTY_CASE);
  const [suiteForm, setSuiteForm] = useState(EMPTY_SUITE);
  const [executionForm, setExecutionForm] = useState({ status: '', actual_result: '', notes: '', evidence_text: '', defect_id: '' });
  const [stepResults, setStepResults] = useState([]);
  const [lastFailedExecution, setLastFailedExecution] = useState(null);
  const [feedback, setFeedback] = useState('');

  const projectsQuery = useQuery({ queryKey: ['qa-projects'], queryFn: qaApi.getProjects });
  const projects = projectsQuery.data || EMPTY_LIST;
  const projectId = selectedProjectId || projects[0]?.id || '';

  const suitesQuery = useQuery({
    queryKey: ['qa-suites', projectId],
    queryFn: () => qaApi.getSuites(projectId),
    enabled: Boolean(projectId),
  });
  const sprintsQuery = useQuery({
    queryKey: ['qa-project-sprints', projectId],
    queryFn: () => sprintsApi.listByProject(projectId),
    enabled: Boolean(projectId),
  });
  const sprints = sprintsQuery.data || EMPTY_LIST;
  const storiesQuery = useQuery({
    queryKey: ['qa-project-stories', projectId, sprints.map((sprint) => sprint.id)],
    queryFn: async () => (await Promise.all(
      sprints.map((sprint) => storiesApi.listBySprint(sprint.id))
    )).flat(),
    enabled: Boolean(projectId) && !sprintsQuery.isLoading && sprints.length > 0,
  });
  const stories = storiesQuery.data || EMPTY_LIST;
  const storyById = useMemo(() => new Map(stories.map((story) => [story.id, story])), [stories]);
  const storyOptions = stories.map((story) => ({
    value: story.id,
    label: `${story.title} (${story.id})`,
  }));
  const casesQuery = useQuery({
    queryKey: ['qa-cases', projectId],
    queryFn: () => qaApi.getCases(projectId, { limit: 500 }),
    enabled: Boolean(projectId),
  });
  const suites = (suitesQuery.data || EMPTY_LIST).filter((suite) => suite.status === 'active');
  const cases = casesQuery.data || EMPTY_LIST;
  const retestCaseId = searchParams.get('caseId');
  const retestDefectId = searchParams.get('defectId');
  const retestCase = retestCaseId && retestDefectId
    ? cases.find((testCase) => testCase.id === retestCaseId)
    : null;
  const selectedCase = storedCase || retestCase;
  const activeModal = modal || (retestCase ? 'execute' : '');
  const executionSteps = stepResults.length
    ? stepResults
    : (selectedCase?.steps || []).map((step) => ({
      step_number: step.step_number,
      actual_result: '',
      status: '',
      comments: '',
    }));
  const executionsQuery = useQuery({
    queryKey: ['qa-executions', selectedCase?.id],
    queryFn: () => qaApi.getExecutions(selectedCase.id),
    enabled: Boolean(selectedCase?.id) && modal === 'detail',
  });
  const visibleCases = useMemo(() => cases.filter((testCase) => {
    const matchesSuite = !suiteFilter || testCase.suite_id === suiteFilter;
    const matchesPriority = !priorityFilter || testCase.priority === priorityFilter;
    const matchesStory = !storyFilter || testCase.story_id === storyFilter;
    const term = search.trim().toLowerCase();
    const matchesSearch = !term || [testCase.id, testCase.title, testCase.story_id]
      .some((value) => value?.toLowerCase().includes(term));
    return matchesSuite && matchesPriority && matchesStory && matchesSearch;
  }), [cases, priorityFilter, search, storyFilter, suiteFilter]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['qa-cases', projectId] });
    queryClient.invalidateQueries({ queryKey: ['qa-suites', projectId] });
    queryClient.invalidateQueries({ queryKey: ['qa-dashboard'] });
  };
  const createSuite = useMutation({
    mutationFn: () => qaApi.createSuite({ project_id: projectId, ...suiteForm, story_id: suiteForm.story_id || null }),
    onSuccess: () => { setModal(''); setSuiteForm(EMPTY_SUITE); setFeedback('Test suite created.'); refresh(); },
    onError: (error) => setFeedback(error.message),
  });
  const updateSuite = useMutation({
    mutationFn: ({ suiteId, data }) => qaApi.updateSuite(suiteId, data),
    onSuccess: (suite) => { setModal(''); setFeedback(suite.status === 'archived' ? 'Test suite archived.' : 'Test suite updated.'); refresh(); },
    onError: (error) => setFeedback(error.message),
  });
  const createCase = useMutation({
    mutationFn: (data) => qaApi.createCase(data),
    onSuccess: () => { setModal(''); setForm(EMPTY_CASE); setFeedback('Test case created.'); refresh(); },
    onError: (error) => setFeedback(error.message),
  });
  const editCase = useMutation({
    mutationFn: ({ caseId, data }) => qaApi.updateCase(caseId, data),
    onSuccess: () => { setModal(''); setFeedback('Test case updated.'); refresh(); },
    onError: (error) => setFeedback(error.message),
  });
  const cloneCase = useMutation({
    mutationFn: qaApi.cloneCase,
    onSuccess: () => { setFeedback('Test case cloned.'); refresh(); },
    onError: (error) => setFeedback(error.message),
  });
  const createExecution = useMutation({
    mutationFn: (data) => qaApi.createExecution(selectedCase.id, data),
    onSuccess: (execution) => {
      setStoredCase(selectedCase);
      if (retestDefectId) navigate('/tests', { replace: true });
      setModal('detail');
      setLastFailedExecution(execution.status === 'FAILED' && !execution.defect_id ? execution : null);
      setExecutionForm({ status: '', actual_result: '', notes: '', evidence_text: '', defect_id: '' });
      setFeedback('Execution saved to history.');
      queryClient.invalidateQueries({ queryKey: ['qa-executions', selectedCase.id] });
      queryClient.invalidateQueries({ queryKey: ['qa-dashboard'] });
    },
    onError: (error) => setFeedback(error.message),
  });
  const createDefect = useMutation({
    mutationFn: () => qaApi.createDefect({
      project_id: selectedCase.project_id,
      test_case_id: selectedCase.id,
      execution_id: lastFailedExecution.id,
      story_id: selectedCase.story_id || null,
      task_id: selectedCase.task_id || null,
      title: `Failed test: ${selectedCase.title}`,
      description: lastFailedExecution.actual_result,
      steps_to_reproduce: selectedCase.steps.map((step) => `${step.step_number}. ${step.instruction}`).join('\n'),
      expected_result: selectedCase.expected_result,
      actual_result: lastFailedExecution.actual_result,
    }),
    onSuccess: (defect) => {
      setLastFailedExecution(null);
      setFeedback(`Defect ${defect.id} created.`);
      queryClient.invalidateQueries({ queryKey: ['qa-dashboard'] });
      navigate('/bugs');
    },
    onError: (error) => setFeedback(error.message),
  });

  const openNewCase = () => {
    setForm({ ...EMPTY_CASE, suite_id: suiteFilter || suites[0]?.id || '' });
    setModal('case');
    setFeedback('');
  };
  const openEditCase = (testCase) => {
    setStoredCase(testCase);
    setForm({
      ...testCase,
      steps_text: testCase.steps.map((step) => `${step.instruction} => ${step.expected_result}`).join('\n'),
    });
    setModal('edit');
    setFeedback('');
  };
  const saveCase = (event) => {
    event.preventDefault();
    const steps = parseSteps(form.steps_text);
    if (!steps.length || steps.some((step) => !step.instruction || !step.expected_result)) {
      setFeedback('Enter each test step as: action => expected result.');
      return;
    }
    const data = {
      ...(modal === 'case' ? { project_id: projectId } : {}),
      suite_id: form.suite_id || null,
      story_id: form.story_id || null,
      task_id: form.task_id || null,
      title: form.title,
      description: form.description,
      objective: form.objective,
      preconditions: form.preconditions,
      steps,
      expected_result: form.expected_result,
      priority: form.priority,
      test_type: form.test_type,
    };
    if (modal === 'edit') editCase.mutate({ caseId: selectedCase.id, data });
    else createCase.mutate(data);
  };
  const openExecution = (testCase) => {
    setStoredCase(testCase);
    setStepResults(testCase.steps.map((step) => ({
      step_number: step.step_number,
      actual_result: '',
      status: '',
      comments: '',
    })));
    setExecutionForm({ status: '', actual_result: '', notes: '', evidence_text: '', defect_id: '' });
    setLastFailedExecution(null);
    setModal('execute');
  };
  const saveExecution = (event) => {
    event.preventDefault();
    if (executionSteps.some((step) => !step.status || !step.actual_result.trim())) {
      setFeedback('Record an actual result and status for every step.');
      return;
    }
    if (!executionForm.status || !executionForm.actual_result.trim()) {
      setFeedback('Select an execution outcome and enter the actual result.');
      return;
    }
    createExecution.mutate({
      test_case_id: selectedCase.id,
      defect_id: executionForm.defect_id || retestDefectId || null,
      status: executionForm.status,
      actual_result: executionForm.actual_result,
      notes: executionForm.notes,
      step_results: executionSteps,
      evidence: executionForm.evidence_text.split('\n').map((value) => value.trim()).filter(Boolean),
    });
  };

  if (projectsQuery.isLoading) return <LoadingState message="Loading authorized QA projects..." />;
  if (projectsQuery.error) return <ErrorState message={projectsQuery.error.message} onRetry={projectsQuery.refetch} />;
  if (suitesQuery.error) return <ErrorState message={suitesQuery.error.message} onRetry={suitesQuery.refetch} />;
  if (casesQuery.error) return <ErrorState message={casesQuery.error.message} onRetry={casesQuery.refetch} />;
  if (sprintsQuery.error) return <ErrorState message={sprintsQuery.error.message} onRetry={sprintsQuery.refetch} />;
  if (storiesQuery.error) return <ErrorState message={storiesQuery.error.message} onRetry={storiesQuery.refetch} />;

  const columns = [
    { key: 'id', header: 'Test Case', render: (item) => <strong>{item.id}</strong> },
    { key: 'title', header: 'Title', render: (item) => item.title },
    { key: 'story_id', header: 'Story', render: (item) => storyById.get(item.story_id)?.title || item.story_id || '—' },
    { key: 'priority', header: 'Priority', render: (item) => <Badge>{item.priority}</Badge> },
    { key: 'test_type', header: 'Type', render: (item) => item.test_type },
    {
      key: 'actions',
      header: 'Actions',
      render: (item) => (
        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
          <Button size="sm" variant="secondary" onClick={() => { setStoredCase(item); setLastFailedExecution(null); setModal('detail'); }}>Details</Button>
          <Button size="sm" variant="primary" onClick={() => openExecution(item)}>Execute</Button>
          <Button size="sm" variant="ghost" onClick={() => openEditCase(item)}>Edit</Button>
          <Button size="sm" variant="ghost" onClick={() => cloneCase.mutate(item.id)}>Clone</Button>
          <Button size="sm" variant="danger" onClick={() => {
            if (window.confirm(`Archive test case "${item.id}"? Its execution history will remain.`)) {
              editCase.mutate({ caseId: item.id, data: { is_archived: true } });
            }
          }}>Archive</Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Test Management"
        subtitle="Manage suites and cases, record manual outcomes, and retain every execution."
        actions={
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ width: 240 }}>
              <Select aria-label="QA project" value={projectId} onChange={(event) => { setSelectedProjectId(event.target.value); setSuiteFilter(''); }} options={projects.map((project) => ({ value: project.id, label: project.name }))} placeholder="Select project" />
            </div>
            <Button variant="secondary" disabled={!projectId} onClick={() => { setSuiteForm(EMPTY_SUITE); setModal('suite'); }}>New Suite</Button>
            <Button variant="primary" disabled={!projectId} onClick={openNewCase}>New Test Case</Button>
          </div>
        }
      />

      {feedback && <p role="status" style={{ color: feedback.includes('created') || feedback.includes('saved') || feedback.includes('updated') || feedback.includes('archived') ? 'var(--success)' : 'var(--danger)' }}>{feedback}</p>}

      <Card title="Test Suites" subtitle="Archiving preserves all linked cases and execution history." style={{ marginBottom: '1.25rem' }}>
        {suites.length ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
            {suites.map((suite) => (
              <div key={suite.id} style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '0.75rem', minWidth: 200 }}>
                <strong>{suite.name}</strong>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{suite.story_id || 'Project suite'}</div>
                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  <Button size="sm" variant="ghost" onClick={() => { setSuiteForm({ ...suite, id: suite.id }); setModal('suite-edit'); }}>Edit</Button>
                  <Button size="sm" variant="ghost" onClick={() => {
                    if (window.confirm(`Archive suite "${suite.name}"? Existing cases and executions will be retained.`)) {
                      updateSuite.mutate({ suiteId: suite.id, data: { status: 'archived' } });
                    }
                  }}>Archive</Button>
                </div>
              </div>
            ))}
          </div>
        ) : <p style={{ color: 'var(--text-muted)' }}>No test suites yet. Create a suite to organize cases.</p>}
      </Card>

      <Card title="Test Cases" subtitle={`${visibleCases.length} active case${visibleCases.length === 1 ? '' : 's'}`}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <SearchInput value={search} onChange={setSearch} placeholder="Search title, ID, or story..." width="300px" />
          <div style={{ width: 220 }}>
            <Select value={suiteFilter} onChange={(event) => setSuiteFilter(event.target.value)} placeholder="All suites" options={suites.map((suite) => ({ value: suite.id, label: suite.name }))} />
          </div>
          <div style={{ width: 180 }}>
            <Select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)} placeholder="All priorities" options={['low', 'medium', 'high', 'critical'].map((value) => ({ value, label: value }))} />
          </div>
          <div style={{ width: 180 }}>
            <Select value={storyFilter} onChange={(event) => setStoryFilter(event.target.value)} placeholder="All stories" options={[...new Set(cases.map((item) => item.story_id).filter(Boolean))].map((value) => ({ value, label: value }))} />
          </div>
        </div>
        <Table columns={columns} data={visibleCases} emptyMessage="No test cases found for this project or filter." />
      </Card>

      <Modal isOpen={modal === 'suite' || modal === 'suite-edit'} onClose={() => setModal('')} title={modal === 'suite-edit' ? 'Edit Test Suite' : 'Create Test Suite'}>
        <form onSubmit={(event) => {
          event.preventDefault();
          if (modal === 'suite-edit') {
            updateSuite.mutate({ suiteId: suiteForm.id, data: { name: suiteForm.name, description: suiteForm.description, story_id: suiteForm.story_id || null } });
          } else {
            createSuite.mutate();
          }
        }} style={{ display: 'grid', gap: '0.85rem' }}>
          <Input label="Suite name" value={suiteForm.name} onChange={(event) => setSuiteForm({ ...suiteForm, name: event.target.value })} required />
          <Input label="Description" value={suiteForm.description} onChange={(event) => setSuiteForm({ ...suiteForm, description: event.target.value })} />
          <Select label="Story (optional)" value={suiteForm.story_id || ''} onChange={(event) => setSuiteForm({ ...suiteForm, story_id: event.target.value })} options={storyOptions} placeholder="Project-wide suite" />
          {feedback && <p role="alert">{feedback}</p>}
          <Button type="submit" isLoading={createSuite.isPending || updateSuite.isPending}>{modal === 'suite-edit' ? 'Save Suite' : 'Create Suite'}</Button>
        </form>
      </Modal>

      <Modal isOpen={modal === 'case' || modal === 'edit'} onClose={() => setModal('')} title={modal === 'edit' ? 'Edit Test Case' : 'Create Test Case'} maxWidth="760px">
        <form onSubmit={saveCase} style={{ display: 'grid', gap: '0.75rem' }}>
          <Input label="Title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required />
          <Input label="Description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          <Input label="Test objective" value={form.objective} onChange={(event) => setForm({ ...form, objective: event.target.value })} />
          <Input label="Preconditions" value={form.preconditions} onChange={(event) => setForm({ ...form, preconditions: event.target.value })} />
          <Input label="Expected overall result" value={form.expected_result} onChange={(event) => setForm({ ...form, expected_result: event.target.value })} required />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
            <Select label="Suite" value={form.suite_id} onChange={(event) => setForm({ ...form, suite_id: event.target.value })} placeholder="No suite" options={suites.map((suite) => ({ value: suite.id, label: suite.name }))} />
            <Select label="Story" value={form.story_id || ''} onChange={(event) => setForm({ ...form, story_id: event.target.value })} options={storyOptions} placeholder="No linked story" />
            <Input label="Task ID" value={form.task_id} onChange={(event) => setForm({ ...form, task_id: event.target.value })} />
            <Select label="Priority" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })} options={['low', 'medium', 'high', 'critical'].map((value) => ({ value, label: value }))} />
            <Select label="Test type" value={form.test_type} onChange={(event) => setForm({ ...form, test_type: event.target.value })} options={['functional', 'negative', 'regression', 'integration', 'smoke', 'other'].map((value) => ({ value, label: value }))} />
          </div>
          <label style={{ display: 'grid', gap: '0.35rem' }}>
            <span>Ordered test steps (one per line: action =&gt; expected result)</span>
            <textarea required rows={5} value={form.steps_text} onChange={(event) => setForm({ ...form, steps_text: event.target.value })} />
          </label>
          {feedback && <p role="alert">{feedback}</p>}
          <Button type="submit" isLoading={createCase.isPending || editCase.isPending}>{modal === 'edit' ? 'Save Changes' : 'Create Test Case'}</Button>
        </form>
      </Modal>

      <Modal isOpen={modal === 'detail'} onClose={() => setModal('')} title={selectedCase?.title || 'Test Case Details'} maxWidth="820px">
        {selectedCase && (
          <div style={{ display: 'grid', gap: '1rem' }}>
            <div><strong>{selectedCase.id}</strong> · {selectedCase.story_id || 'No linked story'} · {selectedCase.priority} {selectedCase.test_type}</div>
            <p>{selectedCase.description}</p>
            <p><strong>Objective:</strong> {selectedCase.objective || '—'}</p>
            <p><strong>Preconditions:</strong> {selectedCase.preconditions || '—'}</p>
            <p><strong>Expected result:</strong> {selectedCase.expected_result}</p>
            <ol>{selectedCase.steps.map((step) => <li key={step.step_number}>{step.instruction} <span style={{ color: 'var(--text-muted)' }}>Expected: {step.expected_result}</span></li>)}</ol>
            {lastFailedExecution && (
              <Card title="Failed execution">
                <p>{lastFailedExecution.actual_result}</p>
                <Button variant="danger" isLoading={createDefect.isPending} onClick={() => createDefect.mutate()}>Create defect from this failure</Button>
              </Card>
            )}
            <Card title="Execution history">
              {executionsQuery.isLoading ? <LoadingState message="Loading execution history..." /> : executionsQuery.error ? <ErrorState message={executionsQuery.error.message} onRetry={executionsQuery.refetch} /> : executionsQuery.data?.length ? (
                executionsQuery.data.map((execution) => <div key={execution.id} style={{ padding: '0.65rem', borderBottom: '1px solid var(--border-subtle)' }}><strong>{execution.status}</strong> · {execution.executed_at} · {execution.executed_by}<p>{execution.actual_result}</p></div>)
              ) : <p>No executions yet. No result is assumed.</p>}
            </Card>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <Button onClick={() => openExecution(selectedCase)}>Execute Test</Button>
              <Button variant="secondary" onClick={() => openEditCase(selectedCase)}>Edit Case</Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal isOpen={activeModal === 'execute'} onClose={() => {
        setModal('');
        if (retestDefectId) navigate('/tests', { replace: true });
      }} title={`Execute ${selectedCase?.id || 'Test Case'}`} maxWidth="820px">
        {selectedCase && (
          <form onSubmit={saveExecution} style={{ display: 'grid', gap: '0.8rem' }}>
            <h3>{selectedCase.title}</h3>
            <p>{selectedCase.description}</p>
            <p><strong>Preconditions:</strong> {selectedCase.preconditions || '—'}</p>
            <p><strong>Expected:</strong> {selectedCase.expected_result}</p>
            {selectedCase.steps.map((step, index) => (
              <Card key={step.step_number} title={`Step ${step.step_number}: ${step.instruction}`} subtitle={`Expected: ${step.expected_result}`}>
                <div style={{ display: 'grid', gap: '0.65rem' }}>
                  <Input label="Actual step result" value={executionSteps[index]?.actual_result || ''} onChange={(event) => setStepResults((all) => (all.length ? all : executionSteps).map((item, position) => position === index ? { ...item, actual_result: event.target.value } : item))} required />
                  <Select label="Step outcome" value={executionSteps[index]?.status || ''} onChange={(event) => setStepResults((all) => (all.length ? all : executionSteps).map((item, position) => position === index ? { ...item, status: event.target.value } : item))} options={EXECUTION_STATUSES.map((value) => ({ value, label: value }))} />
                  <Input label="Step comments" value={executionSteps[index]?.comments || ''} onChange={(event) => setStepResults((all) => (all.length ? all : executionSteps).map((item, position) => position === index ? { ...item, comments: event.target.value } : item))} />
                </div>
              </Card>
            ))}
            <Select label="Overall execution result" value={executionForm.status} onChange={(event) => setExecutionForm({ ...executionForm, status: event.target.value })} options={EXECUTION_STATUSES.map((value) => ({ value, label: value }))} />
            <Input label="Actual overall result" value={executionForm.actual_result} onChange={(event) => setExecutionForm({ ...executionForm, actual_result: event.target.value })} required />
            <Input label="Execution notes" value={executionForm.notes} onChange={(event) => setExecutionForm({ ...executionForm, notes: event.target.value })} />
            <label style={{ display: 'grid', gap: '0.35rem' }}>
              <span>Evidence references (one URL/reference per line; file uploads are not configured)</span>
              <textarea rows={3} value={executionForm.evidence_text} onChange={(event) => setExecutionForm({ ...executionForm, evidence_text: event.target.value })} />
            </label>
            {feedback && <p role="alert">{feedback}</p>}
            <Button type="submit" isLoading={createExecution.isPending}>Save Execution</Button>
          </form>
        )}
      </Modal>
    </div>
  );
}
