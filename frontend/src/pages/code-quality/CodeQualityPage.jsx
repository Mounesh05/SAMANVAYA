import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { projectsApi } from '../../api/projects.api';
import { useAuthStore } from '../../store/useAuthStore';
import { Textarea } from '../../components/common/Textarea';
import { codeQualityApi } from '../../api/codeQuality.api';
import { githubApi } from '../../api/github.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { RiskBadge } from '../../components/common/RiskBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Play, ArrowRight, FolderTree, GitBranch, GitPullRequest } from 'lucide-react';
import { formatDate } from '../../utils/dates';
import { getGradeColor } from '../../utils/formatters';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS } from '../../auth/permissions';
import { AlgorithmComparisonPanel } from './AlgorithmComparisonPanel';
import { BehavioralCompatibilityPanel } from './BehavioralCompatibilityPanel';
import { RequirementsPanel } from './RequirementsPanel';
import { PRAlgorithmIntelligencePanel } from './PRAlgorithmIntelligencePanel';
import { fileScopeLabel, isQualityActive, qualityStatus, qualityTone } from './qualityStatus';
import './CodeQuality.css';

const CUSTOM_REF_VALUE = '__custom__';

const ANALYSIS_MODES = [
  {
    value: 'repository',
    label: 'Whole repository',
    description: 'Analyze all supported files on a branch',
    Icon: GitBranch,
  },
  {
    value: 'selected_files',
    label: 'Selected files',
    description: 'Browse and select files or directories',
    Icon: FolderTree,
  },
  {
    value: 'pr_comparison',
    label: 'PR comparison',
    description: 'Compare base and head PR revisions',
    Icon: GitPullRequest,
  },
];

const emptyForm = {
  repository_id: '', pr_number: '', file_scope: 'repository', analysis_level: 'standard', repository_ref: '',
  changed_files: '', reanalysis_of: undefined, use_ai: true, custom_ref: false,
};

export function CodeQualityPage() {
  const { state } = useLocation();
  const user = useAuthStore((store) => store.user);
  return <QualityHistory key={JSON.stringify([state?.reanalysis?.run_id, user?.org_id, user?.employee_id])} prior={state?.reanalysis} user={user} />;
}

function initialScope(prior) {
  if (!prior) return 'repository';
  if (prior.kind === 'pr_quality_comparison' || prior.file_scope === 'pr_comparison') return 'pr_comparison';
  if (prior.file_scope === 'repository') return 'repository';
  return 'selected_files';
}

function QualityHistory({ prior, user }) {
  const [params, setParams] = useSearchParams();
  const [isAnalyzeModalOpen, setIsAnalyzeModalOpen] = useState(Boolean(prior));
  const [fileFilter, setFileFilter] = useState('');
  const [directory, setDirectory] = useState('');
  const [formData, setFormData] = useState({
    ...emptyForm,
    repository_id: prior?.repository_id || '',
    pr_number: prior?.pr_number ? String(prior.pr_number) : '',
    file_scope: initialScope(prior),
    repository_ref: prior?.repository_ref || '',
    changed_files: (prior?.selected_scope?.length ? prior.selected_scope : prior?.changed_files)?.join('\n') || '',
    reanalysis_of: prior?.run_id,
  });
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const viewer = [user?.org_id, user?.employee_id];
  const projects = useQuery({
    queryKey: ['code-quality', 'projects', ...viewer],
    queryFn: () => projectsApi.list(),
  });
  const projectOptions = (projects.data || []).map(project => ({
    value: project.id, label: project.name || project.id,
  }));
  const selectedRepo = params.get('project') ?? prior?.repository_id
    ?? (projectOptions.length === 1 ? projectOptions[0].value : '');
  if (selectedRepo && !projectOptions.some(project => project.value === selectedRepo)) {
    projectOptions.unshift({ value: selectedRepo, label: selectedRepo });
  }
  const { data: historyData, isLoading, error, refetch } = useQuery({
    queryKey: ['code-quality', 'history', ...viewer, selectedRepo],
    queryFn: () => codeQualityApi.getHistory(selectedRepo, 20),
    enabled: Boolean(selectedRepo),
    refetchInterval: (query) => query.state.data?.history?.some(isQualityActive) ? 3000 : false,
  });
  const connection = useQuery({
    queryKey: ['code-quality', 'repository-connection', ...viewer, formData.repository_id],
    queryFn: () => githubApi.getProjectConfig(formData.repository_id),
    enabled: isAnalyzeModalOpen && Boolean(formData.repository_id),
    retry: false,
  });
  const branchesQuery = useQuery({
    queryKey: ['code-quality', 'branches', ...viewer, formData.repository_id],
    queryFn: () => codeQualityApi.getBranches(formData.repository_id),
    enabled: isAnalyzeModalOpen && Boolean(formData.repository_id) && connection.isSuccess && !formData.reanalysis_of,
    retry: false,
  });

  const defaultBranch = branchesQuery.data?.default_branch || connection.data?.default_branch || '';
  const effectiveBranch = formData.repository_ref.trim() || defaultBranch;

  const filesQuery = useQuery({
    queryKey: ['code-quality', 'files', ...viewer, formData.repository_id, effectiveBranch],
    queryFn: () => codeQualityApi.getRepositoryFiles(formData.repository_id, effectiveBranch || null),
    enabled: isAnalyzeModalOpen && Boolean(formData.repository_id) && connection.isSuccess
      && formData.file_scope === 'selected_files' && !formData.reanalysis_of,
    retry: false,
  });

  const prsQuery = useQuery({
    queryKey: ['code-quality', 'pull-requests', ...viewer, formData.repository_id],
    queryFn: () => codeQualityApi.getPullRequests(formData.repository_id, 'all'),
    enabled: isAnalyzeModalOpen && Boolean(formData.repository_id) && connection.isSuccess
      && formData.file_scope === 'pr_comparison' && !formData.reanalysis_of,
    retry: false,
  });

  const analyzeMutation = useMutation({
    mutationFn: payload => codeQualityApi.startAnalysis(payload),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['code-quality'] });
      setIsAnalyzeModalOpen(false);
      if (res?.run_id) navigate('/code-quality/runs/' + res.run_id);
    },
  });

  const update = (field, value) => setFormData(data => ({ ...data, [field]: value }));
  const changedFiles = [...new Set(formData.changed_files.split('\n').map(path => path.trim()).filter(Boolean))];
  const wholeRevision = formData.file_scope === 'repository';
  const prComparison = formData.file_scope === 'pr_comparison';
  const selectedFilesMode = formData.file_scope === 'selected_files';
  const prNumber = formData.pr_number === '' ? null : Number(formData.pr_number);
  const tooManyPaths = changedFiles.length > 100 || changedFiles.some(path => path.length > 500);
  const validPrNumber = prNumber !== null && Number.isSafeInteger(prNumber) && prNumber > 0;
  const canSubmit = connection.isSuccess && !connection.isFetching && (
    wholeRevision
    || (selectedFilesMode && changedFiles.length > 0 && !tooManyPaths && (prNumber === null || validPrNumber))
    || (prComparison && validPrNumber)
  );

  function toggleSelectedPath(path) {
    const next = changedFiles.includes(path)
      ? changedFiles.filter(item => item !== path)
      : [...changedFiles, path];
    update('changed_files', next.join('\n'));
  }

  function handleModeChange(mode) {
    analyzeMutation.reset();
    setFormData(data => ({
      ...data,
      file_scope: mode,
      pr_number: mode === 'pr_comparison' ? data.pr_number : '',
    }));
  }

  function handleStartAnalysis(event) {
    event.preventDefault();
    if (!canSubmit || analyzeMutation.isPending) return;
    analyzeMutation.mutate({
      repository_id: formData.repository_id,
      file_scope: formData.file_scope,
      analysis_level: formData.analysis_level,
      reanalysis_of: formData.reanalysis_of,
      changed_files: selectedFilesMode ? changedFiles : [],
      repository_ref: prComparison || formData.reanalysis_of ? null : (formData.repository_ref.trim() || null),
      pr_number: prComparison ? prNumber : (selectedFilesMode ? prNumber : null),
      use_ai: !prComparison && formData.analysis_level !== 'purpose_discovery' && formData.use_ai,
    });
  }

  const branchOptions = [];
  const rawBranches = branchesQuery.data?.branches || [];
  if (defaultBranch && !rawBranches.some(b => b.name === defaultBranch)) {
    branchOptions.push({ value: defaultBranch, label: `${defaultBranch} (default)` });
  }
  for (const branch of rawBranches) {
    branchOptions.push({
      value: branch.name,
      label: branch.name === defaultBranch ? `${branch.name} (default)` : branch.name,
    });
  }
  branchOptions.push({ value: CUSTOM_REF_VALUE, label: 'Custom branch or commit SHA…' });

  const prOptions = (prsQuery.data?.pull_requests || []).map(pr => ({
    value: String(pr.number),
    label: `#${pr.number} · ${pr.title || 'Pull request'}${pr.head_ref && pr.base_ref ? ` (${pr.head_ref} → ${pr.base_ref})` : ''} [${pr.state || 'open'}]`,
  }));

  const normalizedFilter = fileFilter.trim().toLowerCase();
  const inDirectory = (path) => !directory || path.startsWith(directory + '/');
  const repoFiles = (filesQuery.data?.files || []).filter(
    path => inDirectory(path) && (!normalizedFilter || path.toLowerCase().includes(normalizedFilter))
  );
  const repoDirs = (filesQuery.data?.directories || []).filter(
    dir => inDirectory(dir) && (!normalizedFilter || dir.toLowerCase().includes(normalizedFilter))
  );

  const runs = historyData?.history || [];

  const columns = [
    { key: 'run_id', header: 'Run ID', render: (r) => <span className="font-mono">{r.run_id}</span> },
    { key: 'file_scope', header: 'Scope', render: fileScopeLabel },
    {
      key: 'target',
      header: 'Branch / PR',
      render: (r) => r.pr_number
        ? <span>PR #{r.pr_number}</span>
        : r.repository_ref
          ? <code>{r.repository_ref}</code>
          : r.commit_sha
            ? <code title={r.commit_sha}>{r.commit_sha.slice(0, 8)}</code>
            : <span className="cq-note">Default</span>,
    },
    { key: 'language', header: 'Language', render: (r) => <span style={{ textTransform: 'capitalize', fontWeight: '600' }}>{r.language && r.language !== 'unknown' ? r.language : 'Undetermined'}</span> },
    {
      key: 'quality_score',
      header: 'Quality score',
      render: (r) => (
        r.quality_score != null ? (
          <span style={{ fontWeight: '600', color: r.quality_grade ? getGradeColor(r.quality_grade) : 'var(--text-primary)' }}>
            {r.quality_score}/100
          </span>
        ) : (
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
            {isQualityActive(r) ? 'Pending' : 'Not measured'}
          </span>
        )
      ),
    },
    {
      key: 'risk_level',
      header: 'Risk',
      render: (r) => r.risk_score != null ? <RiskBadge level={r.risk_level} score={r.risk_score} /> : <span>Not measured</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => (
        <span className="cq-status" data-tone={qualityTone(r)}>
          {qualityStatus(r)}
        </span>
      ),
    },
    { key: 'created_at', header: 'Date', render: (r) => formatDate(r.created_at) },
    {
      key: 'action',
      header: '',
      render: (r) => (
        <Button variant="ghost" size="sm" aria-label={"View run " + r.run_id} rightIcon={<ArrowRight size={14} />} onClick={() => navigate(`/code-quality/runs/${r.run_id}`)}>
          View run
        </Button>
      ),
    },
  ];

  return (
    <div className="cq">
      <PageHeader
        title="Code quality"
        subtitle="Review quality, findings and CI coverage for connected repositories."
        actions={
          <PermissionGuard permission={PERMISSIONS.TRIGGER_CODE_ANALYSIS}>
            <Button
              variant="primary"
              leftIcon={<Play size={16} />}
              onClick={() => {
                analyzeMutation.reset();
                setDirectory('');
                setFileFilter('');
                setFormData({ ...emptyForm, repository_id: selectedRepo });
                setIsAnalyzeModalOpen(true);
              }}
            >
              Start analysis
            </Button>
          </PermissionGuard>
        }
      />

      <Card title="Analysis history" subtitle="Python, JavaScript and TypeScript">
        <div className="cq-filter">
          <Select label="Project" id="quality-history-project" value={selectedRepo} options={projectOptions}
            placeholder={projects.isPending ? 'Loading projects' : 'Select a project'}
            onChange={(event) => setParams({ project: event.target.value }, { replace: true })} />
          {projects.isError && <ErrorState message="Could not load projects." onRetry={projects.refetch} />}
          {projects.isSuccess && !projectOptions.length && <p className="cq-note">No active projects are available to this account.</p>}
        </div>
        {isLoading ? (
          <LoadingState message="Loading analysis history..." />
        ) : error ? (
          <ErrorState message={error.message} onRetry={refetch} />
        ) : (
          <Table
            columns={columns}
            data={runs}
            emptyMessage={selectedRepo ? 'No analysis runs for this project.' : 'Select a project to view its runs.'}
          />
        )}
      </Card>

      <PRAlgorithmIntelligencePanel />

      <details className="cq-advanced">
        <summary>Advanced tools<span>Benchmarks, compatibility and requirements</span></summary>
        <div className="cq-advanced-body cq-panel">
          <AlgorithmComparisonPanel />
          <BehavioralCompatibilityPanel />
          <RequirementsPanel />
        </div>
      </details>

      <PermissionGuard permission={PERMISSIONS.TRIGGER_CODE_ANALYSIS}>
        <Modal
          isOpen={isAnalyzeModalOpen}
          onClose={() => { if (!analyzeMutation.isPending) setIsAnalyzeModalOpen(false); }}
          title={formData.reanalysis_of ? 'Reanalyze revision' : 'Start code quality analysis'}
          maxWidth="640px"
          footer={<>
            <Button variant="secondary" disabled={analyzeMutation.isPending}
              onClick={() => setIsAnalyzeModalOpen(false)}>Cancel</Button>
            <Button variant="primary" type="submit" form="quality-analysis-form"
              disabled={!canSubmit} isLoading={analyzeMutation.isPending}>Run analysis</Button>
          </>}
        >
          <form id="quality-analysis-form" className="cq-form" onSubmit={handleStartAnalysis}>
            {!formData.reanalysis_of && (
              <div className="cq-mode-tabs" role="tablist" aria-label="Analysis mode">
                {ANALYSIS_MODES.map(({ value, label, description, Icon }) => (
                  <button
                    key={value}
                    type="button"
                    role="tab"
                    aria-selected={formData.file_scope === value}
                    className="cq-mode-tab"
                    onClick={() => handleModeChange(value)}
                  >
                    <span className="cq-mode-tab-title">
                      <Icon size={15} aria-hidden="true" />
                      {label}
                    </span>
                    <span className="cq-mode-tab-desc">{description}</span>
                  </button>
                ))}
              </div>
            )}

            {formData.reanalysis_of ? (
              <p className="cq-note">
                Using the recorded commit and scope from <code>{formData.reanalysis_of}</code>
              </p>
            ) : (
              <Select
                label="Analysis project"
                value={formData.repository_id}
                options={projectOptions}
                onChange={(event) => {
                  analyzeMutation.reset();
                  setDirectory('');
                  setFileFilter('');
                  setFormData(data => ({
                    ...data,
                    repository_id: event.target.value,
                    repository_ref: '',
                    custom_ref: false,
                    pr_number: '',
                    changed_files: '',
                  }));
                }}
                required
              />
            )}

            {isAnalyzeModalOpen && formData.repository_id && connection.isFetching && (
              <p role="status" className="cq-note">Checking repository connection…</p>
            )}
            {connection.isError && (connection.error.status === 404
              ? <p role="alert" className="cq-error">This project has no connected GitHub repository.</p>
              : <ErrorState message={connection.error.message} onRetry={connection.refetch} />)}
            {connection.isSuccess && (
              <p className="cq-note">
                Connected repository: <strong>{connection.data.repository_owner}/{connection.data.repository_name}</strong>
                {!formData.reanalysis_of && !prComparison && defaultBranch && !formData.repository_ref && (
                  <> · Default branch <code>{defaultBranch}</code></>
                )}
              </p>
            )}

            {!formData.reanalysis_of && connection.isSuccess && !prComparison && (
              <>
                <Select
                  label="Branch"
                  value={formData.custom_ref ? CUSTOM_REF_VALUE : (formData.repository_ref || defaultBranch)}
                  placeholder={null}
                  options={branchOptions}
                  onChange={(event) => {
                    const val = event.target.value;
                    if (val === CUSTOM_REF_VALUE) {
                      setFormData(data => ({ ...data, custom_ref: true }));
                    } else {
                      setFormData(data => ({
                        ...data,
                        custom_ref: false,
                        repository_ref: val === defaultBranch ? '' : val,
                      }));
                    }
                  }}
                />
                {formData.custom_ref && (
                  <Input
                    label="Branch or commit"
                    maxLength={200}
                    placeholder={defaultBranch || 'main'}
                    value={formData.repository_ref}
                    onChange={(event) => update('repository_ref', event.target.value)}
                  />
                )}
              </>
            )}

            {!formData.reanalysis_of && prComparison && connection.isSuccess && (
              <div className="cq-form">
                {prsQuery.isFetching && <p role="status" className="cq-note">Loading repository pull requests…</p>}
                {prsQuery.isError && (
                  <p role="alert" className="cq-note">
                    Could not load pull requests ({prsQuery.error?.message || 'GitHub unavailable'}). You can still enter a PR number below.
                  </p>
                )}
                {prOptions.length > 0 && (
                  <Select
                    label="Pull request"
                    value={formData.pr_number}
                    placeholder="Select a pull request"
                    options={prOptions}
                    onChange={(event) => update('pr_number', event.target.value)}
                  />
                )}
                <Input
                  label={prOptions.length > 0 ? 'Or enter PR number' : 'Pull request number'}
                  type="number"
                  min="1"
                  step="1"
                  placeholder="e.g. 12"
                  value={formData.pr_number}
                  onChange={(event) => update('pr_number', event.target.value)}
                  required={prOptions.length === 0}
                />
              </div>
            )}

            {selectedFilesMode && (
              <div className="cq-form">
                {!formData.reanalysis_of && connection.isSuccess && (
                  <div className="cq-browser">
                    <div className="cq-browser-header">
                      <Input
                        label="Browse repository files and directories"
                        placeholder="Filter by file or directory path…"
                        value={fileFilter}
                        onChange={(event) => setFileFilter(event.target.value)}
                      />
                    </div>
                    {filesQuery.isFetching && <p role="status" className="cq-note">Discovering supported files…</p>}
                    {filesQuery.isError && (
                      <p className="cq-note">Could not load tree ({filesQuery.error.message}). You can still enter paths below.</p>
                    )}
                    {filesQuery.isSuccess && (
                      <>
                        <p className="cq-note">
                          {filesQuery.data.total_supported_files} supported files on <code>{filesQuery.data.ref}</code>
                          {filesQuery.data.commit_sha ? ` (${filesQuery.data.commit_sha.slice(0, 8)})` : ''} · {changedFiles.length} / {filesQuery.data.max_files_per_run || 100} selected
                        </p>
                        {directory && (
                          <button type="button" className="cq-diff-tab"
                            onClick={() => setDirectory(directory.split('/').slice(0, -1).join('/'))}>
                            Up from {directory}/
                          </button>
                        )}
                        {repoDirs.length > 0 && (
                          <div>
                            <p className="cq-note" style={{ marginBottom: '6px' }}>Directories</p>
                            <div className="cq-chips-row">
                              {repoDirs.slice(0, 20).map(dir => {
                                const dirToken = dir + '/';
                                const active = changedFiles.includes(dirToken) || changedFiles.includes(dir);
                                return (
                                  <span key={dir} className="cq-chips-row">
                                  <button
                                    type="button"
                                    className="cq-diff-tab"
                                    aria-pressed={active}
                                    onClick={() => toggleSelectedPath(dirToken)}
                                  >
                                    {dirToken}
                                  </button>
                                  <button type="button" className="cq-diff-tab" onClick={() => setDirectory(dir)}>
                                    Open {dirToken}
                                  </button>
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        <div className="cq-browser-list" role="group" aria-label="Supported repository files">
                          {repoFiles.slice(0, 150).map(path => (
                            <label key={path} className="cq-browser-item">
                              <input
                                type="checkbox"
                                checked={changedFiles.includes(path)}
                                onChange={() => toggleSelectedPath(path)}
                              />
                              <code>{path}</code>
                            </label>
                          ))}
                          {repoFiles.length === 0 && (
                            <p className="cq-note">No supported Python, JavaScript, or TypeScript files match this filter.</p>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}
                <Textarea
                  label="Changed files"
                  rows={4}
                  value={formData.changed_files}
                  className="input-field cq-paths"
                  helperText="Selected repository-relative files or directories (e.g. backend/api/), one per line. Up to 100 entries."
                  error={tooManyPaths ? 'Use at most 100 paths of up to 500 characters each.' : undefined}
                  onChange={(event) => update('changed_files', event.target.value)}
                  required
                />
              </div>
            )}

            <div className="form-columns">
              <Select
                label="Analysis level"
                value={formData.analysis_level}
                placeholder={null}
                onChange={(event) => update('analysis_level', event.target.value)}
                options={[
                  { value: 'standard', label: 'Standard' },
                  { value: 'quick', label: 'Quick' },
                  { value: 'deep', label: 'Deep' },
                  ...(!prComparison ? [{ value: 'purpose_discovery', label: 'Function discovery only' }] : []),
                ]}
              />
            </div>

            {formData.analysis_level !== 'purpose_discovery' && !prComparison && (
              <label className="cq-checkbox">
                <input
                  type="checkbox"
                  checked={formData.use_ai}
                  onChange={(event) => update('use_ai', event.target.checked)}
                />{' '}
                Include AI suggestions
              </label>
            )}

            <p className="cq-note">
              SAMANVAYA freezes the selected revision to an immutable commit SHA and analyzes Python, JavaScript, and TypeScript without executing untrusted repository code.
            </p>
            {analyzeMutation.error && <p role="alert" className="cq-error">{analyzeMutation.error.message}</p>}
          </form>
        </Modal>
      </PermissionGuard>
    </div>
  );
}
