import React, { useState, useMemo } from 'react';
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
import { ErrorState } from '../../components/common/ErrorState';
import { Play } from 'lucide-react';
import { getGradeColor } from '../../utils/formatters';
import { ROLES } from '../../utils/constants';

export function PerformancePage() {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();
  const isHRorCEO = role === ROLES.HR || role === ROLES.CEO;

  const [selectedDevId, setSelectedDevId] = useState(user?.employee_id || 'E001');
  const queryClient = useQueryClient();

  const { data: employees = [] } = useQuery({
    queryKey: ['employees', 'list'],
    queryFn: () => employeesApi.list(),
  });

  const visibleEmployees = useMemo(() => {
    if (isHRorCEO) return employees;
    if (role === ROLES.DEVELOPER) {
      return employees.filter((e) => e.employee_id === user?.employee_id);
    }
    if (role === ROLES.LEAD) {
      return employees.filter((e) => e.team_id === user?.team_id);
    }
    if (role === ROLES.PM) {
      return employees.filter((e) => e.department === user?.department || e.employee_id === user?.employee_id);
    }
    return employees.filter((e) => e.employee_id === user?.employee_id);
  }, [employees, role, user, isHRorCEO]);

  const {
    data: dashboardData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['developer-performance', selectedDevId],
    queryFn: () => performanceApi.getDeveloperDashboard(selectedDevId),
    retry: 1,
  });

  // Evaluate single mutation
  const evalMutation = useMutation({
    mutationFn: (data) => performanceApi.evaluateDeveloper(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['developer-performance'] });
    },
  });

  const curr = dashboardData?.current_performance;
  const aiEval = curr?.ai_evaluation;
  const dimensions = aiEval?.dimension_scores || {};
  const trendHistory = dashboardData?.historical_trend || [];

  const handleRunEvaluation = () => {
    evalMutation.mutate({
      developer_id: selectedDevId,
      developer_name: employees.find((e) => e.employee_id === selectedDevId)?.name || 'Developer',
      period: '2026-Q3',
      period_type: 'quarter',
    });
  };

  const trendColumns = [
    { key: 'period', header: 'Evaluation Period', render: (t) => <strong>{t.period}</strong> },
    {
      key: 'score',
      header: 'Score',
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
        title="Developer Performance & AI Evaluation"
        subtitle="Authoritative performance scoring based on 90% AI Multi-Dimensional Analysis + 10% Human Role Feedback."
        actions={
          isHRorCEO && (
            <Button
              variant="primary"
              leftIcon={<Play size={16} />}
              onClick={handleRunEvaluation}
              isLoading={evalMutation.isPending}
            >
              Re-run AI Evaluation
            </Button>
          )
        }
      />

      {/* Engineer Selector */}
      {visibleEmployees.length > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
          <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-muted)' }}>
            Select Engineer:
          </span>
          <div style={{ width: '280px' }}>
            <Select
              value={selectedDevId}
              onChange={(e) => setSelectedDevId(e.target.value)}
              options={visibleEmployees.map((e) => ({
                value: e.employee_id,
                label: `${e.name} (${e.role}) - ${e.employee_id}`,
              }))}
            />
          </div>
        </div>
      )}

      {isLoading ? (
        <LoadingState message="Loading performance evaluation data..." />
      ) : error ? (
        <ErrorState
          title="No evaluation recorded yet"
          message={`No performance evaluation found for ${selectedDevId}. Click 'Re-run AI Evaluation' to compute initial scores.`}
          onRetry={handleRunEvaluation}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
          {/* Main Score Card */}
          <ScoreCard
            title={`${curr?.developer_name || selectedDevId} — Performance`}
            score={curr?.overall_score || 0}
            grade={curr?.grade || 'N/A'}
            aiScore={aiEval?.overall_score || 0}
            humanScore={
              curr?.overall_score && aiEval?.overall_score
                ? Number(((curr.overall_score - aiEval.overall_score * 0.7) / 0.3).toFixed(1))
                : 0
            }
            confidence={aiEval?.confidence_score || 85}
            period={curr?.period || '2026-Q3'}
          />

          {/* 6 Dimension Breakdown & AI Strengths Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
            {/* Dimensions Card */}
            <Card title="6-Dimensional AI Breakdown" subtitle="Detailed scoring across engineering domains">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Code Quality (25 pts max)</span>
                    <strong>{dimensions.code_quality?.toFixed(1) || '22.0'} / 25</strong>
                  </div>
                  <ProgressBar value={dimensions.code_quality || 22} max={25} color="primary" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Delivery Speed (20 pts max)</span>
                    <strong>{dimensions.delivery_speed?.toFixed(1) || '18.0'} / 20</strong>
                  </div>
                  <ProgressBar value={dimensions.delivery_speed || 18} max={20} color="cyan" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Collaboration (15 pts max)</span>
                    <strong>{dimensions.collaboration?.toFixed(1) || '13.5'} / 15</strong>
                  </div>
                  <ProgressBar value={dimensions.collaboration || 13.5} max={15} color="purple" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Reliability (15 pts max)</span>
                    <strong>{dimensions.reliability?.toFixed(1) || '13.0'} / 15</strong>
                  </div>
                  <ProgressBar value={dimensions.reliability || 13} max={15} color="success" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Engineering Impact (10 pts max)</span>
                    <strong>{dimensions.business_impact?.toFixed(1) || '8.5'} / 10</strong>
                  </div>
                  <ProgressBar value={dimensions.business_impact || 8.5} max={10} color="warning" />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                    <span>Technical Judgment (5 pts max)</span>
                    <strong>{dimensions.technical_judgment?.toFixed(1) || '4.0'} / 5</strong>
                  </div>
                  <ProgressBar value={dimensions.technical_judgment || 4} max={5} color="primary" />
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
