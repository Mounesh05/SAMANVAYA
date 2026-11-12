import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { transfersApi } from '../../api/transfers.api';
import { employeesApi } from '../../api/employees.api';
import { teamsApi } from '../../api/teams.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { useAuthStore } from '../../store/useAuthStore';
import { hasAnyPermission, TRANSFER_FOR_OTHERS_PERMISSIONS } from '../../auth/permissions';
import { Save, X } from 'lucide-react';

// Values accepted by POST /api/transfers (TransferCreate.reason).
const TRANSFER_REASONS = [
  { value: 'career_growth', label: 'Career growth' },
  { value: 'skill_alignment', label: 'Better skill fit' },
  { value: 'project_needs', label: 'Project needs' },
  { value: 'personal', label: 'Personal reasons' },
  { value: 'grievance_current_manager', label: 'Concern with current manager (goes to HR first)' },
];

const fieldStyle = (hasError) => ({
  width: '100%',
  padding: '0.625rem',
  border: `1px solid ${hasError ? 'var(--error)' : 'var(--border-default)'}`,
  borderRadius: 'var(--radius-md)',
  fontSize: '0.875rem',
  backgroundColor: 'var(--bg-primary)',
  color: 'var(--text-primary)',
  fontFamily: 'inherit',
});

const labelStyle = {
  display: 'block',
  fontSize: '0.875rem',
  fontWeight: '600',
  color: 'var(--text-primary)',
  marginBottom: '0.5rem',
};

function FieldError({ message }) {
  if (!message) return null;
  return (
    <span style={{ fontSize: '0.75rem', color: 'var(--error)', marginTop: '0.25rem', display: 'block' }}>
      {message}
    </span>
  );
}

export function TransferRequestForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  // Managers and HR may file a request for someone else; everyone else
  // requests their own transfer (enforced by the backend as well).
  const canRequestForOthers = hasAnyPermission(user, TRANSFER_FOR_OTHERS_PERMISSIONS);

  const [formData, setFormData] = useState({
    employee_id: canRequestForOthers ? '' : user?.employee_id || '',
    requested_team_id: '',
    reason: '',
    justification: '',
  });
  const [errors, setErrors] = useState({});

  const { data: employeesData, isLoading: employeesLoading } = useQuery({
    queryKey: ['employees'],
    queryFn: () => employeesApi.list(),
    enabled: canRequestForOthers,
  });

  const { data: teamsData, isLoading: teamsLoading } = useQuery({
    queryKey: ['team-directory'],
    queryFn: () => teamsApi.directory(),
  });

  const createMutation = useMutation({
    mutationFn: transfersApi.createTransfer,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['transfers'] });
      navigate(data?.id ? `/transfers/${data.id}` : '/transfers');
    },
    onError: (error) => {
      setErrors({ submit: error.message || 'The transfer request could not be created.' });
    },
  });

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: null, submit: null }));
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.employee_id) newErrors.employee_id = 'Employee is required';
    if (!formData.requested_team_id) newErrors.requested_team_id = 'Target team is required';
    if (!formData.reason) newErrors.reason = 'Choose a reason';
    if (!formData.justification || formData.justification.trim().length < 10) {
      newErrors.justification = 'Explain the request in at least 10 characters';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;
    createMutation.mutate({ ...formData, justification: formData.justification.trim() });
  };

  if ((canRequestForOthers && employeesLoading) || teamsLoading) {
    return <LoadingState message="Loading form data..." />;
  }

  const employees = Array.isArray(employeesData) ? employeesData : employeesData?.employees || [];
  const teams = (Array.isArray(teamsData) ? teamsData : []).filter(
    (team) => canRequestForOthers || team.team_id !== user?.team_id
  );

  return (
    <div>
      <PageHeader
        title={canRequestForOthers ? 'New Transfer Request' : 'Request a Team Transfer'}
        subtitle={
          canRequestForOthers
            ? 'Create a team transfer request for an employee'
            : 'Ask to move to another team. HR reviews your request first.'
        }
      />

      <Card title="Transfer Details" subtitle="Fill in the transfer information">
        <form onSubmit={handleSubmit} style={{ maxWidth: '600px' }}>
          <div style={{ marginBottom: '1.25rem' }}>
            <label htmlFor="employee_id" style={labelStyle}>Employee *</label>
            {canRequestForOthers ? (
              <select
                id="employee_id"
                value={formData.employee_id}
                onChange={(e) => handleChange('employee_id', e.target.value)}
                style={fieldStyle(errors.employee_id)}
              >
                <option value="">Select an employee</option>
                {employees.map((emp) => (
                  <option key={emp.employee_id} value={emp.employee_id}>
                    {emp.name} ({emp.employee_id}) - {emp.role}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="employee_id"
                value={`${user?.name || ''} (${user?.employee_id || ''})`}
                readOnly
                style={fieldStyle(false)}
              />
            )}
            <FieldError message={errors.employee_id} />
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <label htmlFor="requested_team_id" style={labelStyle}>Target Team *</label>
            <select
              id="requested_team_id"
              value={formData.requested_team_id}
              onChange={(e) => handleChange('requested_team_id', e.target.value)}
              style={fieldStyle(errors.requested_team_id)}
            >
              <option value="">Select target team</option>
              {teams.map((team) => (
                <option key={team.team_id} value={team.team_id}>
                  {team.name} ({team.team_id})
                </option>
              ))}
            </select>
            <FieldError message={errors.requested_team_id} />
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <label htmlFor="reason" style={labelStyle}>Reason *</label>
            <select
              id="reason"
              value={formData.reason}
              onChange={(e) => handleChange('reason', e.target.value)}
              style={fieldStyle(errors.reason)}
            >
              <option value="">Select a reason</option>
              {TRANSFER_REASONS.map((reason) => (
                <option key={reason.value} value={reason.value}>{reason.label}</option>
              ))}
            </select>
            <FieldError message={errors.reason} />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label htmlFor="justification" style={labelStyle}>Details *</label>
            <textarea
              id="justification"
              value={formData.justification}
              onChange={(e) => handleChange('justification', e.target.value)}
              rows={4}
              placeholder="Explain why this move makes sense..."
              style={{ ...fieldStyle(errors.justification), resize: 'vertical' }}
            />
            <FieldError message={errors.justification} />
          </div>

          {errors.submit && (
            <div
              role="alert"
              style={{
                padding: '0.75rem',
                backgroundColor: 'var(--error-bg)',
                color: 'var(--error)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.875rem',
                marginBottom: '1rem',
              }}
            >
              {errors.submit}
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <Button type="submit" variant="primary" leftIcon={<Save size={16} />} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Submitting...' : 'Submit Transfer Request'}
            </Button>
            <Button type="button" variant="secondary" leftIcon={<X size={16} />} onClick={() => navigate('/transfers')}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
