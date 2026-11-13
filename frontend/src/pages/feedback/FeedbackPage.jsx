import React, { useState } from 'react';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { employeesApi } from '../../api/employees.api';
import { feedbackApi } from '../../api/feedback.api';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Select } from '../../components/common/Select';
import { ROLES, ROLE_LABELS, designationLabel } from '../../utils/constants';
import { CheckCircle2, Star, Send, Save, AlertCircle, ShieldCheck, Info } from 'lucide-react';
import { useToast } from '../../components/common/Toast';

const HR_DIMENSIONS = [
  {
    key: 'professional_conduct',
    label: 'Professional Conduct',
    description: 'Respectful workplace interactions, professional communication, adherence to conduct guidelines.',
    hasComplianceStatus: false,
  },
  {
    key: 'workplace_ethics',
    label: 'Workplace Ethics & Integrity',
    description: 'Data confidentiality, ethical decision-making, conflict of interest awareness, honesty.',
    hasComplianceStatus: false,
  },
  {
    key: 'policy_compliance',
    label: 'Organizational Policy Compliance',
    description: 'Information security policies, workplace safety, attendance & time recording compliance.',
    hasComplianceStatus: true,
  },
  {
    key: 'mandatory_learning',
    label: 'Mandatory Learning & Compliance',
    description: 'Required organizational trainings, compliance modules, certification renewals.',
    hasComplianceStatus: true,
  },
  {
    key: 'workplace_accountability',
    label: 'Workplace Accountability',
    description: 'Reliability in operational commitments, adherence to HR processes, administrative timeliness.',
    hasComplianceStatus: false,
  },
];

const COMPLIANCE_STATUS_OPTIONS = [
  { value: 'completed', label: 'Completed' },
  { value: 'pending', label: 'Pending' },
  { value: 'exempted', label: 'Exempted' },
  { value: 'under_review', label: 'Under Review' },
];

/**
 * Feedback forms by permission (SUBMIT_*_FEEDBACK), not by role name. The
 * first permission the user holds decides the form; the backend checks the
 * same permission when the feedback is submitted.
 */
const FEEDBACK_KINDS = [
  { key: 'HR', permission: PERMISSIONS.SUBMIT_HR_FEEDBACK, criteria: [], submit: null },
  { key: 'LEAD', permission: PERMISSIONS.SUBMIT_LEAD_FEEDBACK, submit: (id, data) => feedbackApi.submitLeadFeedback(id, data),
    criteria: [
          { key: 'criterion_1', label: 'Technical Skill & Code Hygiene (1-5)' },
          { key: 'criterion_2', label: 'Code Quality & Design Patterns (1-5)' },
          { key: 'criterion_3', label: 'Mentoring & Knowledge Sharing (1-5)' },
          { key: 'criterion_4', label: 'Technical Ownership & Independence (1-5)' },
        ] },
  { key: 'PM', permission: PERMISSIONS.SUBMIT_PM_FEEDBACK, submit: (id, data) => feedbackApi.submitPMFeedback(id, data),
    criteria: [
          { key: 'criterion_1', label: 'Requirement Understanding (1-5)' },
          { key: 'criterion_2', label: 'Delivery Reliability & Timeline (1-5)' },
          { key: 'criterion_3', label: 'Communication & Status Updates (1-5)' },
          { key: 'criterion_4', label: 'Business Alignment & Pragmatism (1-5)' },
        ] },
  { key: 'QA', permission: PERMISSIONS.SUBMIT_QA_FEEDBACK, submit: (id, data) => feedbackApi.submitQAFeedback(id, data),
    criteria: [
          { key: 'criterion_1', label: 'Quality Focus & Defect Prevention (1-5)' },
          { key: 'criterion_2', label: 'Test Coverage & Unit Testing (1-5)' },
          { key: 'criterion_3', label: 'Bug Response & Remediation (1-5)' },
          { key: 'criterion_4', label: 'Regression Awareness (1-5)' },
        ] },
  { key: 'DEVOPS', permission: PERMISSIONS.SUBMIT_DEVOPS_FEEDBACK, submit: (id, data) => feedbackApi.submitDevOpsFeedback(id, data),
    criteria: [
          { key: 'criterion_1', label: 'Deployment Quality & Configurations (1-5)' },
          { key: 'criterion_2', label: 'CI/CD Compliance & Pipeline Care (1-5)' },
          { key: 'criterion_3', label: 'Monitoring & Observability Awareness (1-5)' },
          { key: 'criterion_4', label: 'Incident Response & RCA Support (1-5)' },
        ] },
  { key: 'CEO', permission: PERMISSIONS.SUBMIT_CEO_FEEDBACK, submit: (id, data) => feedbackApi.submitCEOFeedback(id, data),
    criteria: [
          { key: 'criterion_1', label: 'Business Impact & Value Creation (1-5)' },
          { key: 'criterion_2', label: 'Innovation & Creative Solutions (1-5)' },
          { key: 'criterion_3', label: 'Company Mission Alignment (1-5)' },
          { key: 'criterion_4', label: 'Leadership Potential (1-5)' },
        ] },
];

export function FeedbackPage() {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase() || ROLES.LEAD;  // labels only
  // The form follows the feedback permission the user holds (same as the backend).
  const feedbackKind = FEEDBACK_KINDS.find((kind) => hasPermission(user, kind.permission)) || FEEDBACK_KINDS[FEEDBACK_KINDS.length - 1];
  const isHR = feedbackKind.key === 'HR';
  const toast = useToast();
  const queryClient = useQueryClient();

  const [targetEmployeeId, setTargetEmployeeId] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  // Standard role feedback state (non-HR)
  const [ratings, setRatings] = useState({
    criterion_1: 4,
    criterion_2: 4,
    criterion_3: 4,
    criterion_4: 4,
    comments: '',
  });

  // HR workplace assessment state
  const [hrDimensions, setHrDimensions] = useState({
    professional_conduct: { rating: 3, is_not_observed: false, evidence_description: '', comments: '' },
    workplace_ethics: { rating: 3, is_not_observed: false, evidence_description: '', comments: '' },
    policy_compliance: { rating: 3, is_not_observed: false, compliance_status: 'completed', evidence_description: '', comments: '' },
    mandatory_learning: { rating: 3, is_not_observed: false, compliance_status: 'completed', evidence_description: '', comments: '' },
    workplace_accountability: { rating: 3, is_not_observed: false, evidence_description: '', comments: '' },
  });
  const [hrGeneralComments, setHrGeneralComments] = useState('');

  const { data: employees = [] } = useQuery({
    queryKey: ['employees', 'list'],
    queryFn: () => employeesApi.list(),
  });

  // Filter out non-evaluatable roles (CEO, HR) and self, and restrict strictly to engineering contributors.
  // Evaluations are specifically conducted for engineering team members (DEVELOPER, LEAD, QA, DEVOPS).
  const evaluatableEmployees = React.useMemo(() => {
    const eligibleRoles = [ROLES.DEVELOPER, ROLES.LEAD, ROLES.QA, ROLES.DEVOPS];
    return employees.filter((e) => {
      const empRole = e.role?.toUpperCase();
      return (
        eligibleRoles.includes(empRole) &&
        e.employee_id !== 'DEMO-HR' &&
        e.employee_id !== 'DEMO-CEO' &&
        empRole !== ROLES.CEO &&
        empRole !== ROLES.HR &&
        e.employee_id !== user?.employee_id
      );
    });
  }, [employees, user?.employee_id]);

  // Auto-select first eligible engineering employee
  React.useEffect(() => {
    if (evaluatableEmployees.length > 0) {
      if (!targetEmployeeId || !evaluatableEmployees.some((e) => e.employee_id === targetEmployeeId)) {
        setTargetEmployeeId(evaluatableEmployees[0].employee_id);
      }
    }
  }, [evaluatableEmployees, targetEmployeeId]);

  // Load existing assessment or draft for the selected employee if available
  const { data: existingAssessment } = useQuery({
    queryKey: ['hr-assessment', targetEmployeeId],
    queryFn: () => feedbackApi.getHRAssessment(targetEmployeeId),
    enabled: Boolean(isHR && targetEmployeeId),
    retry: false,
  });

  React.useEffect(() => {
    if (existingAssessment?.dimensions) {
      const updated = {};
      HR_DIMENSIONS.forEach((dim) => {
        const item = existingAssessment.dimensions[dim.key];
        if (item) {
          updated[dim.key] = {
            rating: item.rating != null ? item.rating : (item.is_not_observed ? null : 3),
            is_not_observed: Boolean(item.is_not_observed),
            compliance_status: item.compliance_status || (dim.hasComplianceStatus ? 'completed' : undefined),
            evidence_description: item.evidence_description || '',
            comments: item.comments || '',
          };
        } else {
          updated[dim.key] = {
            rating: 3,
            is_not_observed: false,
            compliance_status: dim.hasComplianceStatus ? 'completed' : undefined,
            evidence_description: '',
            comments: '',
          };
        }
      });
      setHrDimensions(updated);
      setHrGeneralComments(existingAssessment.general_comments || '');
    } else {
      setHrDimensions({
        professional_conduct: { rating: 3, is_not_observed: false, evidence_description: '', comments: '' },
        workplace_ethics: { rating: 3, is_not_observed: false, evidence_description: '', comments: '' },
        policy_compliance: { rating: 3, is_not_observed: false, compliance_status: 'completed', evidence_description: '', comments: '' },
        mandatory_learning: { rating: 3, is_not_observed: false, compliance_status: 'completed', evidence_description: '', comments: '' },
        workplace_accountability: { rating: 3, is_not_observed: false, evidence_description: '', comments: '' },
      });
      setHrGeneralComments('');
    }
  }, [existingAssessment]);

  const criteria = feedbackKind.criteria;

  // Mutation for standard non-HR roles
  const submitStandardMutation = useMutation({
    mutationFn: async (data) => {
      return feedbackKind.submit(targetEmployeeId, data);
    },
    onSuccess: () => {
      setSuccessMessage('Feedback recorded and human component updated.');
      setSubmitted(true);
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to submit feedback');
    },
  });

  // Mutation for HR Assessment (Draft & Final Submit)
  const hrSubmitMutation = useMutation({
    mutationFn: async ({ isDraft }) => {
      const perfId = targetEmployeeId;
      const formattedDimensions = {};

      Object.entries(hrDimensions).forEach(([key, val]) => {
        formattedDimensions[key] = {
          dimension: key,
          rating: val.is_not_observed ? null : val.rating,
          is_not_observed: val.is_not_observed,
          compliance_status: val.compliance_status || null,
          evidence_description: val.evidence_description || null,
          comments: val.comments || null,
        };
      });

      const payload = {
        dimensions: formattedDimensions,
        general_comments: hrGeneralComments,
      };

      if (isDraft) {
        return feedbackApi.saveHRAssessmentDraft(perfId, payload);
      } else {
        return feedbackApi.submitHRAssessment(perfId, payload);
      }
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['hr-assessment', targetEmployeeId] });
      queryClient.invalidateQueries({ queryKey: ['developer-performance'] });
      if (variables.isDraft) {
        toast.success('HR assessment draft saved successfully.');
      } else {
        setSuccessMessage('HR Performance Assessment finalized. 90% AI + 10% Human overall score recalculated.');
        setSubmitted(true);
      }
    },
    onError: (err) => {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to save HR assessment';
      toast.error(msg);
    },
  });

  const handleStandardSubmit = (e) => {
    e.preventDefault();
    if (!targetEmployeeId) return;
    submitStandardMutation.mutate({
      ...ratings,
      evaluated_by: user?.employee_id,
    });
  };

  const handleHRSubmit = (e, isDraft) => {
    e.preventDefault();
    if (!targetEmployeeId) return;

    if (!isDraft) {
      // Validate evidence requirements for ratings 1 and 2
      for (const dim of HR_DIMENSIONS) {
        const item = hrDimensions[dim.key];
        if (!item.is_not_observed && (item.rating === 1 || item.rating === 2)) {
          const evidence = (item.evidence_description || '').trim();
          if (evidence.length < 15) {
            toast.error(
              `Dimension "${dim.label}" has a rating of ${item.rating} which requires documented substantiated evidence (minimum 15 characters).`
            );
            return;
          }
        }
      }
    }

    hrSubmitMutation.mutate({ isDraft });
  };

  const handleDimensionRatingChange = (key, ratingValue) => {
    setHrDimensions((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        rating: ratingValue,
        is_not_observed: ratingValue === null,
      },
    }));
  };

  const handleDimensionFieldChange = (key, field, value) => {
    setHrDimensions((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        [field]: value,
      },
    }));
  };

  return (
    <div>
      <PageHeader
        title={isHR ? 'HR Workplace Performance Assessment' : 'Role-Specific Human Feedback'}
        subtitle={
          isHR
            ? "Submit formal HR workplace assessment. Contributes HR's authorized share to the 10% human evaluation component within the 90% AI + 10% Human framework."
            : `Submit formal human evaluation as ${ROLE_LABELS[role] || role}. Contributes to the developer's 10% human evaluation component.`
        }
      />

      <div style={{ maxWidth: isHR ? '800px' : '640px', margin: '0 auto' }}>
        <Card
          title={isHR ? 'Workplace Conduct & Policy Assessment' : `Feedback Submission (${ROLE_LABELS[role] || role})`}
          subtitle={
            isHR
              ? 'Objective rubric: 4=Exceeds, 3=Meets, 2=Needs Improvement, 1=Unsatisfactory, N/O=Not Observed'
              : 'Structured 1-5 scoring with qualitative notes'
          }
        >
          {submitted ? (
            <div style={{ padding: '2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
              <CheckCircle2 size={48} style={{ color: 'var(--success)' }} />
              <h3 style={{ fontSize: '1.25rem', fontWeight: '800', color: 'var(--text-primary)' }}>
                Assessment Submitted Successfully
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', maxWidth: '450px' }}>
                {successMessage}
              </p>
              <Button
                variant="primary"
                onClick={() => {
                  setSubmitted(false);
                  setTargetEmployeeId('');
                }}
              >
                Evaluate Another Employee
              </Button>
            </div>
          ) : isHR ? (
            /* ==================== HR WORKPLACE ASSESSMENT FORM ==================== */
            <form onSubmit={(e) => handleHRSubmit(e, false)} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* HR Information Banner */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.75rem',
                  padding: '0.875rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(59, 130, 246, 0.08)',
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                  fontSize: '0.8125rem',
                  color: 'var(--text-secondary)',
                  lineHeight: '1.45',
                }}
              >
                <Info size={18} style={{ color: 'var(--primary)', flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <strong style={{ color: 'var(--primary)' }}>HR Role Boundary & Evaluation Guidelines:</strong>
                  <br />
                  HR evaluates workplace conduct, policy compliance, mandatory learning, and accountability. HR does NOT evaluate technical code or commits. Ratings 1 and 2 require documented evidence. N/O (Not Observed) is excluded from scoring without penalty.
                </div>
              </div>

              <Select
                label="Target Employee"
                value={targetEmployeeId}
                onChange={(e) => setTargetEmployeeId(e.target.value)}
                placeholder="Select employee to evaluate"
                options={evaluatableEmployees.map((e) => ({
                  value: e.employee_id,
                  label: `${e.name} (${e.role}${e.designation ? ` - ${designationLabel(e.designation)}` : ''}) - ${e.employee_id}`,
                }))}
                required
              />

              {/* 5 HR Dimensions */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {HR_DIMENSIONS.map((dim) => {
                  const state = hrDimensions[dim.key];
                  const isNegativeRating = !state.is_not_observed && (state.rating === 1 || state.rating === 2);
                  const evidenceLen = (state.evidence_description || '').trim().length;

                  return (
                    <div
                      key={dim.key}
                      style={{
                        padding: '1.125rem',
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: 'var(--bg-card-subtle, rgba(255, 255, 255, 0.03))',
                        border: isNegativeRating && evidenceLen < 15
                          ? '1px solid var(--warning, #f59e0b)'
                          : '1px solid var(--border-default)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.85rem',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.95rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                            {dim.label}
                          </span>
                          {state.is_not_observed && (
                            <span
                              style={{
                                fontSize: '0.75rem',
                                fontWeight: '700',
                                padding: '0.15rem 0.5rem',
                                borderRadius: 'var(--radius-sm)',
                                backgroundColor: 'rgba(100, 116, 139, 0.15)',
                                color: 'var(--text-muted)',
                              }}
                            >
                              Excluded (No Penalty)
                            </span>
                          )}
                        </div>
                        <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                          {dim.description}
                        </p>
                      </div>

                      {/* Rubric Buttons: 4, 3, 2, 1, N/O */}
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        {[
                          { val: 4, label: '4 — Exceeds' },
                          { val: 3, label: '3 — Meets' },
                          { val: 2, label: '2 — Needs Imp.' },
                          { val: 1, label: '1 — Unsatisfactory' },
                          { val: null, label: 'N/O — Not Observed' },
                        ].map(({ val, label }) => {
                          const isSelected = val === null ? state.is_not_observed : !state.is_not_observed && state.rating === val;
                          return (
                            <button
                              key={label}
                              type="button"
                              onClick={() => handleDimensionRatingChange(dim.key, val)}
                              style={{
                                flex: '1 1 auto',
                                minWidth: '110px',
                                padding: '0.55rem 0.75rem',
                                borderRadius: 'var(--radius-md)',
                                border: `1px solid ${isSelected ? 'var(--primary)' : 'var(--border-default)'}`,
                                backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'var(--bg-input)',
                                color: isSelected ? 'var(--primary)' : 'var(--text-secondary)',
                                fontWeight: isSelected ? '700' : '500',
                                fontSize: '0.8125rem',
                                cursor: 'pointer',
                                textAlign: 'center',
                                transition: 'all 0.15s ease',
                              }}
                            >
                              {label}
                            </button>
                          );
                        })}
                      </div>

                      {/* Compliance Status Selector (for Compliance & Learning dimensions) */}
                      {dim.hasComplianceStatus && (
                        <div style={{ width: '220px', marginTop: '0.25rem' }}>
                          <Select
                            label="Compliance Status"
                            value={state.compliance_status || 'completed'}
                            onChange={(e) => handleDimensionFieldChange(dim.key, 'compliance_status', e.target.value)}
                            options={COMPLIANCE_STATUS_OPTIONS}
                          />
                        </div>
                      )}

                      {/* Required Evidence Description for ratings 1 and 2 */}
                      {isNegativeRating && (
                        <div
                          style={{
                            marginTop: '0.5rem',
                            padding: '0.75rem',
                            borderRadius: 'var(--radius-sm)',
                            backgroundColor: 'rgba(245, 158, 11, 0.08)',
                            border: '1px solid rgba(245, 158, 11, 0.3)',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.35rem' }}>
                            <AlertCircle size={15} style={{ color: 'var(--warning, #f59e0b)' }} />
                            <span style={{ fontSize: '0.8125rem', fontWeight: '700', color: 'var(--warning, #f59e0b)' }}>
                              Documented Evidence Required (Min 15 chars)
                            </span>
                          </div>
                          <textarea
                            rows={2}
                            value={state.evidence_description || ''}
                            onChange={(e) => handleDimensionFieldChange(dim.key, 'evidence_description', e.target.value)}
                            placeholder="Describe the documented observation, incident log, or verifiable records..."
                            style={{
                              width: '100%',
                              padding: '0.55rem 0.75rem',
                              fontSize: '0.8125rem',
                              backgroundColor: 'var(--bg-input)',
                              color: 'var(--text-primary)',
                              border: `1px solid ${evidenceLen < 15 ? 'var(--warning, #f59e0b)' : 'var(--border-default)'}`,
                              borderRadius: 'var(--radius-sm)',
                              outline: 'none',
                            }}
                          />
                          <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: '0.75rem', color: evidenceLen < 15 ? 'var(--warning, #f59e0b)' : 'var(--text-muted)', marginTop: '0.25rem' }}>
                            {evidenceLen}/15 characters minimum
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* General HR Comments */}
              <div>
                <label style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                  General HR Workplace Observations & Development Notes
                </label>
                <textarea
                  rows={3}
                  value={hrGeneralComments}
                  onChange={(e) => setHrGeneralComments(e.target.value)}
                  placeholder="Additional context on workplace conduct, professional development plans, or organizational support..."
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

              {/* Action Buttons: Save Draft vs Submit */}
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                <Button
                  type="button"
                  variant="secondary"
                  size="md"
                  isLoading={hrSubmitMutation.isPending && hrSubmitMutation.variables?.isDraft}
                  leftIcon={<Save size={16} />}
                  onClick={(e) => handleHRSubmit(e, true)}
                  disabled={!targetEmployeeId}
                >
                  Save Assessment Draft
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  isLoading={hrSubmitMutation.isPending && !hrSubmitMutation.variables?.isDraft}
                  leftIcon={<ShieldCheck size={16} />}
                  disabled={!targetEmployeeId}
                >
                  Submit Final Assessment
                </Button>
              </div>
            </form>
          ) : (
            /* ==================== STANDARD ROLE FEEDBACK FORM (NON-HR) ==================== */
            <form onSubmit={handleStandardSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <Select
                label="Target Engineer"
                value={targetEmployeeId}
                onChange={(e) => setTargetEmployeeId(e.target.value)}
                placeholder="Select engineer to evaluate"
                options={evaluatableEmployees.map((e) => ({
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
                          background: ratings[c.key] === val ? 'rgba(59, 130, 246, 0.15)' : 'var(--bg-input)',
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
                isLoading={submitStandardMutation.isPending}
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
