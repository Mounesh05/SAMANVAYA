import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/client';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { useSessionScope } from '../../store/useSessionScope';

export function ReleaseGateSettings({ projectId }) {
  const session = useSessionScope();
  const [credential, setCredential] = useState(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const [confirmation, setConfirmation] = useState(null);
  const path = `/projects/${encodeURIComponent(projectId)}/release-gate`;
  const gate = useQuery({
    queryKey: ['release-gate-settings', session, projectId], queryFn: () => apiClient.get(path),
    enabled: Boolean(projectId), retry: false,
  });
  const current = gate.data;
  function requestChange(action) {
    const repository = action === 'issue' ? current.linked_repository : current.repository;
    const request = { action, repository, version: current.version };
    if (current.enabled) setConfirmation({ request, previousRepository: current.repository });
    else change(request);
  }
  async function change(request) {
    setConfirmation(null);
    setPending(true);
    setCredential(null);
    setMessage('');
    try {
      const result = await apiClient.post(path, request);
      if (result.token) setCredential({ value: result.token, version: result.version });
    } catch (error) {
      setMessage(error.message || 'Credential update failed.');
    } finally {
      await gate.refetch();
      setPending(false);
    }
  }
  return <Card title="Production release gate" style={{ marginBottom: '1.5rem' }}>
    {!projectId ? <p>Enter the project ID above to manage workflow access.</p>
      : gate.isError ? <p role="alert">{gate.error.message} <Button size="sm" onClick={() => gate.refetch()}>Retry</Button></p>
      : !current ? <p role="status">Loading credential status…</p>
      : <>
        <p>{current.enabled ? `Credential active for ${current.repository}.` : 'No active workflow credential.'}
          {' '}{current.linked_repository ? `Linked repository: ${current.linked_repository}.` : 'A unique repository link is required to issue a credential.'}</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          {current.linked_repository && <Button size="sm" disabled={pending}
            onClick={() => requestChange('issue')}>{current.enabled ? 'Replace credential' : 'Issue credential'}</Button>}
          {current.enabled && <Button size="sm" variant="danger" disabled={pending}
            onClick={() => requestChange('revoke')}>Revoke credential</Button>}
        </div>
        {credential && current.enabled && credential.version === current.version && <div style={{ marginTop: '1rem' }}>
          <Input label="One-time release gate token" type="password" readOnly autoComplete="off" value={credential.value}
            helperText="Save this as SAMANVAYA_RELEASE_GATE_TOKEN in the production environment of the linked repository." />
          <Button size="sm" variant="secondary" onClick={() => setCredential(null)}>Dismiss token</Button>
        </div>}
      </>}
    {message && <p role="alert">{message}</p>}
    {confirmation && !gate.isError && <ConfirmDialog isOpen isDangerous
      title={confirmation.request.action === 'issue' ? 'Replace release credential?' : 'Revoke release credential?'}
      message={`Workflows using the current credential for ${confirmation.previousRepository} will lose access immediately.`}
      confirmLabel={confirmation.request.action === 'issue' ? 'Replace' : 'Revoke'}
      onClose={() => setConfirmation(null)} onConfirm={() => change(confirmation.request)} />}
  </Card>;
}
