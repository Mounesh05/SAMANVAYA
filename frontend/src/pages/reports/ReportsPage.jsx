/**
 * Reports page — evaluation report generation and download
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { reportsApi } from '../../api/reports.api';
import { employeesApi } from '../../api/employees.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { formatDate } from '../../utils/dates';
import { FileBarChart, Download, Plus, AlertCircle } from 'lucide-react';
import { Modal } from '../../components/common/Modal';
import toast from 'react-hot-toast';

const reportSchema = z.object({
  developer_id: z.string().min(1, 'Select a developer'),
  period: z.string().min(1, 'Enter period'),
  report_type: z.enum(['performance', 'code_quality', 'comprehensive']),
});

function ReportForm({ onSuccess, onCancel }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(reportSchema),
    defaultValues: { report_type: 'comprehensive' },
  });

  const { data: empData } = useQuery({
    queryKey: ['employees-list'],
    queryFn: () => employeesApi.list({ role: 'DEVELOPER' }).then(r => Array.isArray(r.data) ? r.data : r.data?.employees || []),
  });

  const developers = (empData || []).filter(e => e.role === 'DEVELOPER');

  const onSubmit = async (data) => {
    try {
      const result = await reportsApi.generate(data.developer_id, data.period, { report_type: data.report_type });
      toast.success('Report generated successfully');
      onSuccess(result.data);
    } catch (err) {
      toast.error(err.userMessage || 'Failed to generate report');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
        <div className="form-group">
          <label className="form-label required" htmlFor="rpt-dev">Developer</label>
          <select id="rpt-dev" className={`form-control${errors.developer_id ? ' error' : ''}`}
            {...register('developer_id')}>
            <option value="">Select developer…</option>
            {developers.map(d => (
              <option key={d.employee_id} value={d.employee_id}>{d.name}</option>
            ))}
          </select>
          {errors.developer_id && <span className="form-error"><AlertCircle size={12} />{errors.developer_id.message}</span>}
        </div>
        <div className="form-group">
          <label className="form-label required" htmlFor="rpt-period">Period</label>
          <input id="rpt-period" className={`form-control${errors.period ? ' error' : ''}`}
            placeholder="e.g. 2026-Q3" {...register('period')} />
          {errors.period && <span className="form-error"><AlertCircle size={12} />{errors.period.message}</span>}
        </div>
        <div className="form-group">
          <label className="form-label required" htmlFor="rpt-type">Report Type</label>
          <select id="rpt-type" className="form-control" {...register('report_type')}>
            <option value="comprehensive">Comprehensive</option>
            <option value="performance">Performance Only</option>
            <option value="code_quality">Code Quality Only</option>
          </select>
        </div>
      </div>
      <div className="modal-footer">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting && <span className="spinner" style={{ width: 14, height: 14 }} />}
          Generate Report
        </button>
      </div>
    </form>
  );
}

export function ReportsPage() {
  const [generateOpen, setGenerateOpen] = useState(false);
  const [reports, setReports] = useState([]);

  const handleReportGenerated = (reportData) => {
    setGenerateOpen(false);
    if (reportData) setReports(prev => [reportData, ...prev]);
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Reports</h1>
          <p className="page-subtitle">Generate and download performance reports</p>
        </div>
        <button className="btn btn-primary" onClick={() => setGenerateOpen(true)}>
          <Plus size={16} /> Generate Report
        </button>
      </div>

      {reports.length === 0 ? (
        <div className="card">
          <EmptyState
            title="No reports generated"
            description="Generate a performance or code quality report for a developer"
            action={
              <button className="btn btn-primary" onClick={() => setGenerateOpen(true)}>
                <FileBarChart size={16} /> Generate Report
              </button>
            }
          />
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Developer</th>
                <th>Period</th>
                <th>Type</th>
                <th>Generated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r, i) => (
                <tr key={r._id || i}>
                  <td style={{ fontWeight: 500 }}>{r.developer_name || r.developer_id}</td>
                  <td>{r.period}</td>
                  <td><span className="badge badge-brand">{r.report_type}</span></td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>{formatDate(r.generated_at || new Date().toISOString())}</td>
                  <td>
                    <button className="btn btn-secondary btn-sm" onClick={() => {/* download */ }}>
                      <Download size={14} /> Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal isOpen={generateOpen} onClose={() => setGenerateOpen(false)} title="Generate Report">
        <ReportForm onSuccess={handleReportGenerated} onCancel={() => setGenerateOpen(false)} />
      </Modal>
    </div>
  );
}
