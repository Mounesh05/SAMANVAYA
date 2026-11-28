import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'react-router-dom';
import { codeQualityApi } from '../../api/codeQuality.api';
import { algorithmsApi } from '../../api/algorithms.api';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { Card } from '../../components/common/Card';
import { useSessionScope } from '../../store/useSessionScope';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { AnalysisReport } from './AnalysisReport';

export function RepositoryAnalysis({ projectId }) {
  const scope = useSessionScope();
  const user = useAuthStore(s => s.user);
  const [mode, setMode] = useState('repository');
  const [ref, setRef] = useState('');
  const [paths, setPaths] = useState([]);
  const [search, setSearch] = useState('');
  const [pr, setPR] = useState('');
  const files = useQuery({ queryKey: ['algorithm-paths', scope, projectId, ref],
    queryFn: () => codeQualityApi.getRepositoryFiles(projectId, ref || null), enabled: mode === 'selected_files', retry:false });
  const prs = useQuery({ queryKey: ['algorithm-prs', scope, projectId], queryFn: () => algorithmsApi.getPRIntelligence({ project_id:projectId }),
    enabled: mode === 'pull_request', retry:false });
  const submit = useMutation({ mutationFn: () => codeQualityApi.startAnalysis({ repository_id:projectId, analysis_level:'purpose_discovery',
    file_scope:mode, repository_ref:ref.trim() || null, changed_files:mode === 'selected_files' ? paths : [], use_ai:false }) });
  const options = [...(files.data?.directories || []).map(d => d + '/'), ...(files.data?.files || [])].filter(p => p.toLowerCase().includes(search.toLowerCase()));
  const matches = (prs.data?.analyses || []).filter(r => r.project_id === projectId && String(r.pr_number) === pr);
  return <Card title="Analyze source" className="ai-stack"><div className="ai-fields">
    <Select label="Source scope" placeholder={null} value={mode} options={[{value:'repository',label:'Repository'},{value:'selected_files',label:'Selected files or directories'},{value:'pull_request',label:'Pull request'}]}
      onChange={e => {setMode(e.target.value);submit.reset();}} />
    {mode !== 'pull_request' && <Input label="Branch or commit" placeholder="Repository default" value={ref} onChange={e => {setRef(e.target.value);setPaths([]);submit.reset();}} />}
    {mode === 'pull_request' && <Select label="Pull request" value={pr} options={[...new Set((prs.data?.analyses || []).filter(r=>r.project_id===projectId).map(r => String(r.pr_number)))].map(n=>({value:n,label:'#'+n}))} onChange={e=>setPR(e.target.value)} />}
  </div>
    {mode === 'selected_files' && <div className="ai-stack"><Input label="Find files or directories" type="search" value={search} onChange={e=>setSearch(e.target.value)} />
      {files.isError ? <p role="alert">Could not load files at this revision.</p> : files.isPending ? <p>Loading files…</p> :
        <div className="ai-paths">{options.map(path => <label key={path}><input type="checkbox" checked={paths.includes(path)} disabled={!paths.includes(path) && paths.length >= 100}
          onChange={e=>setPaths(e.target.checked ? [...paths,path] : paths.filter(p=>p!==path))} /> {path}</label>)}</div>}</div>}
    {mode === 'pull_request' ? <>{prs.isError && <p role="alert">Pull request reports unavailable.</p>}{prs.isSuccess && !matches.length && <p>Select an analyzed pull request to inspect its revisions.</p>}
      {matches.map(r=><a key={r.run_id} href={'/algorithm-intelligence/pr/'+encodeURIComponent(r.run_id)+'?project='+encodeURIComponent(projectId)}>{r.head_sha?.slice(0,12)} · {r.status}</a>)}</> :
      hasPermission(user, PERMISSIONS.TRIGGER_CODE_ANALYSIS) && <Button isLoading={submit.isPending} disabled={mode === 'selected_files' && (!paths.length || !files.isSuccess)} onClick={()=>submit.mutate()}>Start function discovery</Button>}
    {submit.error && <p role="alert">{submit.error.message}</p>}{submit.data?.run_id && <a href={'/algorithm-intelligence/discovery/'+encodeURIComponent(submit.data.run_id)+'?project='+encodeURIComponent(projectId)}>Open discovery report</a>}
  </Card>;
}

export function AlgorithmRunPage() {
  const { kind, runId } = useParams();
  const [params] = useSearchParams();
  const projectId = params.get('project');
  const scope = useSessionScope();
  const isPR = kind === 'pr';
  const result = useQuery({queryKey:['algorithm-report',scope,projectId,kind,runId], enabled:Boolean(projectId && ['pr','discovery'].includes(kind)), retry:false,
    queryFn: async () => {
      if (isPR) return (await algorithmsApi.getPRIntelligence({project_id:projectId,run_id:runId})).analyses.find(r=>r.run_id===runId && r.project_id===projectId) || null;
      const doc=await codeQualityApi.getRun(runId);
      if (doc.run_id !== runId || doc.repository_id !== projectId) return null;
      return {...doc, project_id:projectId, functions:(doc.function_discovery?.functions || []).map(current=>({current,
        status:'analyzed',static_status:'analyzed',complexity:current.structure?.static_cost,static:{test_expectations:(current.evidence || []).filter(e=>e.kind==='test_expectation')},
        evidence_refs:(current.evidence || []).map(e=>e.id)})), analysis_truncated:doc.is_truncated || doc.function_discovery?.truncated};
    },refetchInterval:q=>['pending','running','analyzing','benchmarking'].includes(q.state.data?.status) ? 3000 : false});
  return <main className="ai-workspace"><a href={'/algorithm-intelligence'+(projectId?'?project='+encodeURIComponent(projectId):'')}>Algorithm Intelligence</a>
    <Card title={isPR?'Pull request analysis':'Function discovery'}>
      {!projectId || result.isError || !['pr','discovery'].includes(kind) || (result.isSuccess && !result.data) ? <p role="alert">Report unavailable for this project.</p> :
        result.isPending ? <p>Loading report…</p> : <AnalysisReport key={scope+runId} run={result.data} kind={kind} refresh={()=>result.refetch()}
          onReview={()=>window.location.assign('/algorithm-intelligence?section=Requirements&project='+encodeURIComponent(projectId))}/>}
    </Card></main>;
}
