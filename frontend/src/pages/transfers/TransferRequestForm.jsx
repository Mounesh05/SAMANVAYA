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
import { ErrorState } from '../../components/common/ErrorState';
import { useAuthStore } from '../../store/useAuthStore';
import { Save, X } from 'lucide-react';

export function TransferRequestForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  const [formData, setFormData] = useState({
    employee_id: '',
    to_team_id: '',
    reason: '',
  });

  const [errors, setErrors] = useState({});

  // Fetch employees for dropdown
  const { data: employeesData, isLoading: employeesLoading } = useQuery({
    queryKey: ['employees'],
    queryFn: () => employeesApi.list(),
  });

  // Fetch teams for dropdown
  const { data: teamsData, isLoading: teamsLoading } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: transfersApi.createTransfer,
    onSuccess: (data) => {
      queryClient.invalidateQueries(['transfers']);
      navigate(`/transfers/${data.transfer_id}`);
    },
    onError: (error) => {
      setErrors({ submit: error.message });
    },
  });

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: null, submit: null }));
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.employee_id) newErrors.employee_id = 'Employee is required';
    if (!formData.to_team_id) newErrors.to_team_id = 'Target team is required';
    if (!formData.reason || formData.reason.trim().length < 10) {
      newErrors.reason = 'Reason must be at least 10 characters';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;
    createMutation.mutate(formData);
  };

  if (employeesLoading || teamsLoading) {
    return <LoadingState message="Loading form data..." />;
  }

  const employees = employeesData?.employees || [];
  const teams = teamsData?.teams || [];

  return (
    <div>
      <PageHeader
        title="New Transfer Request"
        subtitle="Create a team transfer request for an employee"
      />

      <Card title="Transfer Details" subtitle="Fill in the transfer information">
        <form onSubmit={handleSubmit} style={{ maxWidth: '600px' }}>
          {/* Employee Selection */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label
              htmlFor="employee_id"
              style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: '600',
                color: 'var(--text-primary)',
                marginBottom: '0.5rem',
              }}
            >
              Employee *
            </label>
            <select
              id="employee_id"
              value={formData.employee_id}
              onChange={(e) => handleChange('employee_id', e.target.value)}
              style={{
                width: '100%',
                padding: '0.625rem',
                border: `1px solid ${errors.employee_id ? 'var(--error)' : 'var(--border-default)'}`,
                borderRadius: 'var(--radius-md)',
                fontSize: '0.875rem',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
              }}
            >
              <option value="">Select an employee</option>
              {employees.map((emp) => (
                <option key={emp.employee_id} value={emp.employee_id}>
                  {emp.name} ({emp.employee_id}) - {emp.role}
                </option>
              ))}
            </select>
            {errors.employee_id && (
              <span style={{ fontSize: '0.75rem', color: 'var(--error)', marginTop: '0.25rem', display: 'block' }}>
                {errors.employee_id}
              </span>
            )}
          </div>

          {/* Target Team Selection */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label
              htmlFor="to_team_id"
              style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: '600',
                color: 'var(--text-primary)',
                marginBottom: '0.5rem',
              }}
            >
              Target Team *
            </label>
            <select
              id="to_team_id"
              value={formData.to_team_id}
              onChange={(e) => handleChange('to_team_id', e.target.value)}
              style={{
                width: '100%',
                padding: '0.625rem',
                border: `1px solid ${errors.to_team_id ? 'var(--error)' : 'var(--border-default)'}`,
                borderRadius: 'var(--radius-md)',
                fontSize: '0.875rem',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
              }}
            >
              <option value="">Select target team</option>
              {teams.map((team) => (
                <option key={team.team_id} value={team.team_id}>
                  {team.team_name} ({team.team_id})
                </option>
              ))}
            </select>
            {errors.to_team_id && (
              <span style={{ fontSize: '0.75rem', color: 'var(--error)', marginTop: '0.25rem', display: 'block' }}>
                {errors.to_team_id}
              </span>
            )}
          </div>

          {/* Reason */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label
              htmlFor="reason"
              style={{
                display: 'block',
                fontSize: '0.875rem',
                fontWeight: '600',
                color: 'var(--text-primary)',
                marginBottom: '0.5rem',
              }}
            >
              Reason for Transfer *
            </label>
            <textarea
              id="reason"
              value={formData.reason}
              onChange={(e) => handleChange('reason', e.target.value)}
              rows={4}
              placeholder="Provide a detailed reason for this transfer request..."
              style={{
                width: '100%',
                padding: '0.625rem',
                border: `1px solid ${errors.reason ? 'var(--error)' : 'var(--border-default)'}`,
                borderRadius: 'var(--radius-md)',
                fontSize: '0.875rem',
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
            />
            {errors.reason && (
              <span style={{ fontSize: '0.75rem', color: 'var(--error)', marginTop: '0.25rem', display: 'block' }}>
                {errors.reason}
              </span>
            )}
          </div>

          {/* Submit Error */}
          {errors.submit && (
            <div
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

          {/* Actions */}
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <Button
              type="submit"
              variant="primary"
              leftIcon={<Save size={16} />}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Transfer Request'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              leftIcon={<X size={16} />}
              onClick={() => navigate('/transfers')}
            >
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
