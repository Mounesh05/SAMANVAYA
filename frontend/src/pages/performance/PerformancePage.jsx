import React, { useState, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { performanceApi } from '../../api/performance.api';
import { employeesApi } from '../../api/employees.api';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { ScoreCard } from '../../components/common/ScoreCard';
import { Button } from '../../components/common/Button';
import { Select } from '../../components/common/Select';
import { ProgressBar } from '../../components/common/ProgressBar';
import { LoadingState } from '../../components/common/LoadingState';

import { EmptyState } from '../../components/common/EmptyState';
import { Play, Sparkles, Shield, UserCheck, Award, BookOpen } from 'lucide-react';
import { getGradeColor } from '../../utils/formatters';
import { ROLES } from '../../utils/constants';
import { hasPermission, hasAnyPermission, PERMISSIONS } from '../../auth/permissions';
import { useToast } from '../../components/common/Toast';

function getCurrentQuarterLabel(date = new Date()) {
  return `${date.getFullYear()}-Q${Math.floor(date.getMonth() / 3) + 1}`;
}

const ELIGIBLE_ENGINEERING_ROLES = [
  ROLES.DEVELOPER,
  ROLES.LEAD,
  ROLES.QA,
  ROLES.DEVOPS,
];

export function PerformancePage() {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();
  const isHR = role === ROLES.HR;
  const isCEO = role === ROLES.CEO;
  const isDeveloperUser = role === ROLES.DEVELOPER;
  // Same rule as the backend: TRIGGER_AI_EVALUATION (Lead, CEO, admins).
  const canTriggerEvaluation = hasPermission(user, PERMISSIONS.TRIGGER_AI_EVALUATION);
  // CR-001: without a team/project/organisation performance permission a user
  // sees only their own record, whatever the URL asks for.
  const ownRecordOnly = !hasAnyPermission(user, [
    PERMISSIONS.VIEW_TEAM_PERFORMANCE,
    PERMISSIONS.VIEW_PROJECT_PERFORMANCE,
    PERMISSIONS.VIEW_ORGANIZATION_PERFORMANCE,
    PERMISSIONS.VIEW_PERFORMANCE_OUTCOMES,
  ]);
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const requestedDevId = searchParams.get('developer');

  const queryClient = useQueryClient();

  const { data: employees = [] } = useQuery({
    queryKey: ['employees', 'list'],
    queryFn: () => employeesApi.list(),
    enabled: !ownRecordOnly,
  });

  // Filter out non-evaluatable roles (CEO and HR) and limit strictly to engineering contributors.
  // The 90% AI + 10% Human model evaluates engineering/technical personnel only.
  const visibleEmployees = useMemo(() => {
    const evaluatable = employees.filter((e) => {
      const empRole = e.role?.toUpperCase();
      return (
        ELIGIBLE_ENGINEERING_ROLES.includes(empRole) &&
        e.employee_id !== 'DEMO-HR' &&
        e.employee_id !== 'DEMO-CEO' &&
        empRole !== ROLES.CEO &&
        empRole !== ROLES.HR
      );
    });

    if (isHR || isCEO) return evaluatable;
    if (isDeveloperUser) {
      return evaluatable.filter((e) => e.employee_id === user?.employee_id);
    }
    if (role === ROLES.LEAD) {
      return evaluatable.filter((e) => e.team_id === user?.team_id);
    }
    if (role === ROLES.PM) {
      return evaluatable.filter((e) => e.dept === user?.dept || e.department === user?.department);
    }
    return evaluatable.filter((e) => e.employee_id === user?.employee_id);
  }, [employees, role, user, isHR, isCEO, isDeveloperUser]);

  // Selected developer ID: default to developer themselves if engineer,
  // or requested from URL query param (if not HR/CEO), or empty until evaluatable list loads.
  const [selectedDevId, setSelectedDevId] = useState(() => {
    if (ownRecordOnly) {
      return user?.employee_id || '';
    }
    if (requestedDevId && requestedDevId !== 'DEMO-HR' && requestedDevId !== 'DEMO-CEO') {
      return requestedDevId;
    }
    if (isDeveloperUser && user?.employee_id !== 'DEMO-HR' && user?.employee_id !== 'DEMO-CEO') {
      return user?.employee_id || '';
    }
    return '';
  });

  useEffect(() => {
    if (ownRecordOnly || visibleEmployees.length === 0) return;

    if (requestedDevId && requestedDevId !== 'DEMO-HR' && requestedDevId !== 'DEMO-CEO' && visibleEmployees.some((e) => e.employee_id === requestedDevId)) {
      setSelectedDevId(requestedDevId);
      return;
    }

    // If currently selected ID is invalid or empty or not an evaluatable engineer, select the first valid engineer
    if (!selectedDevId || !visibleEmployees.some((e) => e.employee_id === selectedDevId)) {
      setSelectedDevId(visibleEmployees[0].employee_id);
    }
  }, [visibleEmployees, requestedDevId, selectedDevId, ownRecordOnly]);

  const shownDevId = ownRecordOnly ? user?.employee_id || '' : selectedDevId;

  const {
    data: dashboardData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['developer-performance', shownDevId],
    queryFn: () => performanceApi.getDeveloperDashboard(shownDevId),
    enabled: Boolean(shownDevId) && shownDevId !== 'DEMO-HR' && shownDevId !== 'DEMO-CEO',
    retry: 1,
  });

  // Evaluate single mutation (CEO/Lead only - HR cannot trigger engineering evaluation)
  const evalMutation = useMutation({
    mutationFn: (data) => performanceApi.evaluateDeveloper(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['developer-performance'] });
      toast.success('Contribution credit calculated successfully.');
    },
    onError: (mutationError) => {
      const message = mutationError?.response?.data?.detail
        || mutationError?.message
        || 'The evaluation could not be completed.';
      
      if (message.includes('503') || message.includes('unavailable') || message.includes('Ollama')) {
        toast.error('AI evaluation service is unavailable. Please start Ollama and try again.');
      } else {
        toast.error(message);
      }
    },
  });

  const isHRView = dashboardData?.is_hr_view || isHR;
  const curr = dashboardData?.current_performance;
  const aiEval = curr?.ai_evaluation;
  const dimensions = aiEval?.dimension_scores || {};
  const trendHistory = dashboardData?.historical_trend || [];
  const hrAssessment = dashboardData?.hr_assessment;

  const handleRunEvaluation = () => {
    evalMutation.mutate({
      developer_id: selectedDevId,
      developer_name: employees.find((e) => e.employee_id === selectedDevId)?.name || 'Developer',
      period: getCurrentQuarterLabel(),
      period_type: 'quarter',
    });
  };

  const trendColumns = [
    { key: 'period', header: 'Evaluation Period', render: (t) => <strong>{t.period}</strong> },
    {
      key: 'score',
      header: 'Overall Score',
      render: (t) => (
        <span style={{ fontWeight: '800', color: getGradeColor(t.grade) }}>
          {typeof t.score === 'number' ? t.score.toFixed(1) : t.score}%
        </span>
      ),
    },
    {
      key: 'grade',
      header: 'Grade',
      render: (t) => (
        <span style={{ fontWeight: '700', color: getGradeColor(t.grade) }}>Grade {t.grade}</span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title={isHRView ? 'Employee Performance Outcomes' : 'Developer Performance & AI Evaluation'}
        subtitle={
          isHRView
            ? 'Approved performance outcomes, 90/10 evaluation summary, workplace assessments, and career growth.'
            : 'Evidence-based contribution credit with AI explanations and human feedback.'
        }
        actions={
          canTriggerEvaluation && (
            <Button
              variant="primary"
              leftIcon={<Play size={16} />}
              onClick={handleRunEvaluation}
              isLoading={evalMutation.isPending}
            >
              {evalMutation.isPending ? 'Calculating contribution credit...' : 'Recalculate Contribution Credit'}
            </Button>
          )
        }
      />

      {/* Engineer / Employee Selector */}
      {(visibleEmployees.length > 1 || isHR || isCEO) && visibleEmployees.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
          <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-muted)' }}>
            Select {isHRView ? 'Employee' : 'Engineer'}:
          </span>
          <div style={{ width: '320px' }}>
            <Select
              value={selectedDevId}
              onChange={(e) => setSelectedDevId(e.target.value)}
              options={visibleEmployees.map((e) => ({
                value: e.employee_id,
                label: `${e.name} (${e.role}${e.designation ? ` - ${e.designation}` : ''}) - ${e.employee_id}`,
              }))}
            />
          </div>
        </div>
      )}

      {!selectedDevId || isLoading ? (
        <LoadingState message="Loading performance evaluation data..." />
      ) : error ? (
        <EmptyState
          title={error.message?.includes('503') || error.message?.includes('unavailable') 
            ? "AI Service Unavailable" 
            : "No evaluation recorded yet"}
          description={error.message?.includes('503') || error.message?.includes('unavailable')
            ? "The AI evaluation service (Ollama) is not running. Start Ollama and retry the evaluation."
            : `No performance outcome is recorded for ${selectedDevId} yet.`}
          icon={<Sparkles size={28} />}
          actionLabel={canTriggerEvaluation ? 'Calculate contribution credit' : null}
          onAction={canTriggerEvaluation ? handleRunEvaluation : null}
        />
      ) : isHRView ? (
        /* ==================== HR-SAFE PERFORMANCE VIEW ==================== */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
          {/* Main Score Card for HR */}
          <ScoreCard
            title={`${curr?.developer_name || selectedDevId} — Approved Performance`}
            score={curr?.overall_score ?? curr?.final_score ?? null}
            grade={curr?.grade || 'N/A'}
            aiScore={null}
            humanScore={null}
            confidence={curr?.ai_evaluation?.confidence_score || 85}
            period={curr?.period || curr?.period_label || 'Current Period'}
          />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem' }}>
            {/* 90/10 Score Summary Card */}
            <Card title="90% AI + 10% Human Evaluation Model" subtitle="Weighted performance governance summary">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-default)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Sparkles size={16} style={{ color: 'var(--primary)' }} />
                    <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>AI Evaluation Component (90% weight)</span>
                  </div>
                  <strong style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>
                    {curr?.ai_evaluation?.overall_score != null ? `${curr.ai_evaluation.overall_score.toFixed(1)} / 90` : 'Pending'}
                  </strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-default)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <UserCheck size={16} style={{ color: 'var(--success)' }} />
                    <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Human Evaluation Component (10% weight)</span>
                  </div>
                  <strong style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>
                    {curr?.human_evaluation_summary?.average_score != null ? `${curr.human_evaluation_summary.average_score.toFixed(1)} / 100` : 'Pending'}
                  </strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Award size={16} style={{ color: 'var(--cyan)' }} />
                    <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-primary)' }}>Performance Tier</span>
                  </div>
                  <span style={{ fontWeight: '700', color: getGradeColor(curr?.grade) }}>
                    {curr?.rating || (curr?.grade ? `Grade ${curr.grade}` : 'Under Review')}
                  </span>
                </div>

                {curr?.human_evaluation_summary?.roles_evaluated?.length > 0 && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    Participating evaluators: {curr.human_evaluation_summary.roles_evaluated.map(r => r.toUpperCase()).join(', ')}
                  </div>
                )}
              </div>
            </Card>

            {/* HR Workplace Assessment Card */}
            <Card title="HR Workplace Assessment" subtitle="Workplace conduct, compliance & organizational accountability">
              {hrAssessment ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Overall Workplace Score:</span>
                    <strong style={{ fontSize: '1.1rem', color: 'var(--primary)' }}>
                      {hrAssessment.overall_hr_score != null ? `${hrAssessment.overall_hr_score.toFixed(1)} / 100` : 'Draft'}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    <span>Assessment Status:</span>
                    <span style={{ fontWeight: '600', textTransform: 'uppercase', color: hrAssessment.status === 'submitted' ? 'var(--success)' : 'var(--warning)' }}>
                      {hrAssessment.status}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    <span>Evaluator:</span>
                    <span>{hrAssessment.evaluator_name || hrAssessment.evaluator_id || 'HR'}</span>
                  </div>
                  {hrAssessment.general_comments && (
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.5rem', fontStyle: 'italic', borderTop: '1px solid var(--border-default)', paddingTop: '0.5rem' }}>
                      "{hrAssessment.general_comments}"
                    </p>
                  )}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem', padding: '1rem 0' }}>
                  <Shield size={32} style={{ color: 'var(--text-muted)' }} />
                  <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>No HR workplace assessment submitted for this period.</span>
                </div>
              )}
            </Card>

            {/* Professional Development & Growth Recommendations */}
            <Card title="Professional Growth & Development" subtitle="Actionable recommendations for career progression">
              {aiEval?.recommendations && aiEval.recommendations.length > 0 ? (
                <ul style={{ paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {aiEval.recommendations.map((r, idx) => (
                    <li key={idx}>{r}</li>
                  ))}
                </ul>
              ) : (
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  No development recommendations recorded for this cycle.
                </span>
              )}
            </Card>
          </div>

          {/* Historical Trend Table */}
          {trendHistory.length > 0 && (
            <Card title="Historical Performance Trends" subtitle="Performance scores across evaluation periods">
              <Table columns={trendColumns} data={trendHistory} emptyMessage="No prior periods available." />
            </Card>
          )}
        </div>
      ) : (
        /* ==================== ENGINEERING / LEADERSHIP VIEW ==================== */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
          {/* Main Score Card */}
          <ScoreCard
            title={`${curr?.developer_name || selectedDevId} — Performance`}
            score={curr?.overall_score ?? curr?.final_score ?? null}
            grade={curr?.grade || 'N/A'}
            aiScore={null}
            humanScore={null}
            confidence={curr?.contribution_credit?.confidence === 'high' ? 100 : curr?.contribution_credit?.confidence === 'medium' ? 70 : 40}
            period={curr?.period || curr?.period_label || 'No evaluation period'}
          />

          {/* AI explanation and deterministic contribution breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
            <Card title="Contribution Credit" subtitle="Deterministic score from observed engineering evidence">
              {curr?.contribution_credit ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <strong>{curr.contribution_credit.score.toFixed(1)} / 100</strong>
                  <span>Confidence: {curr.contribution_credit.confidence}</span>
                  {curr.contribution_credit.missing_evidence?.length > 0 && (
                    <span style={{ color: 'var(--text-muted)' }}>
                      Missing evidence: {curr.contribution_credit.missing_evidence.join(', ')}
                    </span>
                  )}
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                    Advisory only. This score should not be used alone for compensation or promotion.
                  </span>
                </div>
              ) : (
                <span>No contribution credit has been calculated yet.</span>
              )}
            </Card>
            {/* Dimensions Card */}
            <Card title="AI Explanation" subtitle="Advisory analysis of the observed evidence">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Code Quality (25 pts max)</span>
                    <strong>{dimensions.code_quality?.toFixed(1) || '0.0'} / 25</strong>
                  </div>
                  <ProgressBar value={dimensions.code_quality || 0} max={25} color="primary" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Delivery Speed (20 pts max)</span>
                    <strong>{dimensions.delivery_speed?.toFixed(1) || '0.0'} / 20</strong>
                  </div>
                  <ProgressBar value={dimensions.delivery_speed || 0} max={20} color="cyan" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Collaboration (15 pts max)</span>
                    <strong>{dimensions.collaboration?.toFixed(1) || '0.0'} / 15</strong>
                  </div>
                  <ProgressBar value={dimensions.collaboration || 0} max={15} color="purple" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Reliability (15 pts max)</span>
                    <strong>{dimensions.reliability?.toFixed(1) || '0.0'} / 15</strong>
                  </div>
                  <ProgressBar value={dimensions.reliability || 0} max={15} color="success" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Engineering Impact (10 pts max)</span>
                    <strong>{dimensions.business_impact?.toFixed(1) || '0.0'} / 10</strong>
                  </div>
                  <ProgressBar value={dimensions.business_impact || 0} max={10} color="warning" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Technical Judgment (5 pts max)</span>
                    <strong>{dimensions.technical_judgment?.toFixed(1) || '0.0'} / 5</strong>
                  </div>
                  <ProgressBar value={dimensions.technical_judgment || 0} max={5} color="primary" />
                </div>
              </div>
            </Card>

            {/* AI Insights, Strengths & Growth Areas */}
            <Card title="Strengths & Growth Areas" subtitle="Extracted from commit diffs & PR discussions">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                {aiEval?.strengths && aiEval.strengths.length > 0 && (
                  <div>
                    <h5 style={{ fontSize: '0.8125rem', fontWeight: '700', color: 'var(--success)', marginBottom: '0.35rem' }}>
                      Key Strengths
                    </h5>
                    <ul style={{ paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      {aiEval.strengths.map((s, idx) => (
                        <li key={idx}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {aiEval?.recommendations && aiEval.recommendations.length > 0 && (
                  <div>
                    <h5 style={{ fontSize: '0.8125rem', fontWeight: '700', color: 'var(--cyan)', marginBottom: '0.35rem' }}>
                      Growth Recommendations
                    </h5>
                    <ul style={{ paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      {aiEval.recommendations.map((r, idx) => (
                        <li key={idx}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Historical Trend Table */}
          {trendHistory.length > 0 && (
            <Card title="Historical Performance Trends" subtitle="Performance scores across evaluation periods">
              <Table columns={trendColumns} data={trendHistory} emptyMessage="No prior periods available." />
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
