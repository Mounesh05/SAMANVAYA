import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { employeesApi } from '../../api/employees.api';
import { feedbackApi } from '../../api/feedback.api';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Select } from '../../components/common/Select';
import { ROLES, ROLE_LABELS } from '../../utils/constants';
import { MessageSquareQuote, CheckCircle2, Star, Send } from 'lucide-react';

export function FeedbackPage() {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase() || ROLES.LEAD;

  const [targetEmployeeId, setTargetEmployeeId] = useState('');
  const [ratings, setRatings] = useState({
    criterion_1: 4,
    criterion_2: 4,
    criterion_3: 4,
    criterion_4: 4,
    comments: '',
  });
  const [submitted, setSubmitted] = useState(false);

  const { data: employees = [] } = useQuery({
    queryKey: ['employees', 'list'],
    queryFn: () => employeesApi.list(),
  });

  const getFeedbackCriteria = () => {
    switch (role) {
      case ROLES.LEAD:
        return [
          { key: 'criterion_1', label: 'Technical Skill & Code Hygiene (1-5)' },
          { key: 'criterion_2', label: 'Code Quality & Design Patterns (1-5)' },
          { key: 'criterion_3', label: 'Mentoring & Knowledge Sharing (1-5)' },
          { key: 'criterion_4', label: 'Technical Ownership & Independence (1-5)' },
        ];
      case ROLES.PM:
        return [
          { key: 'criterion_1', label: 'Requirement Understanding (1-5)' },
          { key: 'criterion_2', label: 'Delivery Reliability & Timeline (1-5)' },
          { key: 'criterion_3', label: 'Communication & Status Updates (1-5)' },
          { key: 'criterion_4', label: 'Business Alignment & Pragmatism (1-5)' },
        ];
      case ROLES.QA:
        return [
          { key: 'criterion_1', label: 'Quality Focus & Defect Prevention (1-5)' },
          { key: 'criterion_2', label: 'Test Coverage & Unit Testing (1-5)' },
          { key: 'criterion_3', label: 'Bug Response & Remediation (1-5)' },
          { key: 'criterion_4', label: 'Regression Awareness (1-5)' },
        ];
      case ROLES.DEVOPS:
        return [
          { key: 'criterion_1', label: 'Deployment Quality & Configurations (1-5)' },
          { key: 'criterion_2', label: 'CI/CD Compliance & Pipeline Care (1-5)' },
          { key: 'criterion_3', label: 'Monitoring & Observability Awareness (1-5)' },
          { key: 'criterion_4', label: 'Incident Response & RCA Support (1-5)' },
        ];
      case ROLES.HR:
        return [
          { key: 'criterion_1', label: 'Collaboration & Team Dynamics (1-5)' },
          { key: 'criterion_2', label: 'Professionalism & Integrity (1-5)' },
          { key: 'criterion_3', label: 'Communication Skills (1-5)' },
          { key: 'criterion_4', label: 'Cultural Fit & Company Values (1-5)' },
        ];
      case ROLES.CEO:
      default:
        return [
          { key: 'criterion_1', label: 'Business Impact & Value Creation (1-5)' },
          { key: 'criterion_2', label: 'Innovation & Creative Solutions (1-5)' },
          { key: 'criterion_3', label: 'Company Mission Alignment (1-5)' },
          { key: 'criterion_4', label: 'Leadership Potential (1-5)' },
        ];
    }
  };

  const criteria = getFeedbackCriteria();

  const submitMutation = useMutation({
    mutationFn: async (data) => {
      // Find performance ID or use target employee id
      const perfId = targetEmployeeId;
      switch (role) {
        case ROLES.LEAD:
          return feedbackApi.submitLeadFeedback(perfId, data);
        case ROLES.PM:
          return feedbackApi.submitPMFeedback(perfId, data);
        case ROLES.QA:
          return feedbackApi.submitQAFeedback(perfId, data);
        case ROLES.DEVOPS:
          return feedbackApi.submitDevOpsFeedback(perfId, data);
        case ROLES.HR:
          return feedbackApi.submitHRFeedback(perfId, data);
        case ROLES.CEO:
        default:
          return feedbackApi.submitCEOFeedback(perfId, data);
      }
    },
    onSuccess: () => {
      setSubmitted(true);
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!targetEmployeeId) return;

    submitMutation.mutate({
      ...ratings,
      evaluated_by: user?.employee_id,
    });
  };

  return (
    <div>
      <PageHeader
        title="Role-Specific Human Feedback"
        subtitle={`Submit formal human evaluation as ${ROLE_LABELS[role] || role}. Contributes 10% weighted authority to the developer's final score.`}
      />

      <div style={{ maxWidth: '640px', margin: '0 auto' }}>
        <Card title={`Feedback Submission (${ROLE_LABELS[role] || role})`} subtitle="Structured 1-5 scoring with qualitative notes">
          {submitted ? (
            <div style={{ padding: '2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
              <CheckCircle2 size={48} style={{ color: 'var(--success)' }} />
              <h3 style={{ fontSize: '1.25rem', fontWeight: '800', color: 'var(--text-primary)' }}>
                Feedback Submitted Successfully
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', maxWidth: '400px' }}>
                Your ratings have been recorded and the engineer's weighted performance score has been updated.
              </p>
              <Button
                variant="primary"
                onClick={() => {
                  setSubmitted(false);
                  setTargetEmployeeId('');
                }}
              >
                Submit Another Feedback
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <Select
                label="Target Engineer"
                value={targetEmployeeId}
                onChange={(e) => setTargetEmployeeId(e.target.value)}
                placeholder="Select engineer to evaluate"
                options={employees.map((e) => ({
                  value: e.employee_id,
                  label: `${e.name} (${e.role}) - ${e.employee_id}`,
                }))}
                required
              />

              {criteria.map((c) => (
                <div key={c.key}>
                  <label style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                    {c.label}
                  </label>
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.35rem' }}>
                    {[1, 2, 3, 4, 5].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => setRatings({ ...ratings, [c.key]: val })}
                        style={{
                          flex: 1,
                          padding: '0.5rem',
                          borderRadius: 'var(--radius-md)',
                          border: `1px solid ${ratings[c.key] === val ? 'var(--primary)' : 'var(--border-default)'}`,
                          background: ratings[c.key] === val ? 'var(--primary-light)' : 'var(--bg-input)',
                          color: ratings[c.key] === val ? 'var(--primary)' : 'var(--text-secondary)',
                          fontWeight: '700',
                          fontSize: '0.95rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '0.25rem',
                        }}
                      >
                        <Star size={14} fill={ratings[c.key] === val ? 'currentColor' : 'none'} />
                        {val}
                      </button>
                    ))}
                  </div>
                </div>
              ))}

              <div>
                <label style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                  Qualitative Comments & Feedback
                </label>
                <textarea
                  rows={4}
                  value={ratings.comments}
                  onChange={(e) => setRatings({ ...ratings, comments: e.target.value })}
                  placeholder="Provide constructive feedback, key accomplishments, or areas for growth..."
                  style={{
                    width: '100%',
                    padding: '0.65rem 0.85rem',
                    fontSize: '0.875rem',
                    backgroundColor: 'var(--bg-input)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-md)',
                    outline: 'none',
                    marginTop: '0.35rem',
                  }}
                />
              </div>

              <Button
                type="submit"
                variant="primary"
                size="lg"
                isLoading={submitMutation.isPending}
                leftIcon={<Send size={16} />}
                disabled={!targetEmployeeId}
              >
                Submit Role Feedback
              </Button>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
