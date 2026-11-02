import { useState, useEffect } from 'react';
import { dashboardAPI, hrAPI, employeesAPI } from '../../services/api';
import { Users, Mail, UserPlus, Award, Send } from 'lucide-react';
import StatsCard from '../../components/StatsCard';
import AnimatedCard from '../../components/AnimatedCard';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

export default function HRDashboard() {
    const [totalEmployees, setTotalEmployees] = useState(0);
    const [candidates, setCandidates] = useState([]);
    const [weeklyData, setWeeklyData] = useState([]);
    const [inviteEmail, setInviteEmail] = useState('');
    const [inviteRole, setInviteRole] = useState('');

    useEffect(() => {
        // 1. Total employees count from user_logins
        employeesAPI.getAll()
            .then(emps => setTotalEmployees(Array.isArray(emps) ? emps.length : 0))
            .catch(() => { });

        // 2. All candidates from HR pipeline (invitations + onboarding)
        hrAPI.hrCandidates()
            .then(data => {
                if (Array.isArray(data)) {
                    setCandidates(data);
                    // Build weekly chart from appliedDate grouping
                    buildWeeklyChart(data);
                }
            })
            .catch(() => { });

        // 3. Dashboard aggregates (weekly_data etc.) — override chart if available
        dashboardAPI.hr()
            .then(data => {
                if (!data) return;
                if (data.weekly_data?.length) setWeeklyData(data.weekly_data);
            })
            .catch(() => { });
    }, []);

    // Group candidates by week of appliedDate to build the hires/departures chart
    const buildWeeklyChart = (cands) => {
        const weeks = {};
        cands.forEach(c => {
            const weekLabel = c.appliedDate
                ? `Week ${Math.ceil(new Date(c.appliedDate).getDate() / 7)}`
                : 'Week 1';
            if (!weeks[weekLabel]) weeks[weekLabel] = { week: weekLabel, hires: 0, departures: 0 };
            if (c.status === 'Hired') weeks[weekLabel].hires += 1;
            else if (c.status === 'Rejected') weeks[weekLabel].departures += 1;
        });
        const chart = Object.values(weeks);
        if (chart.length) setWeeklyData(chart);
    };

    // Derived stats
    const recentInvitations = candidates.slice(0, 10); // most recent candidates = invitations
    const pendingInvitations = candidates.filter(c => c.status === 'Screening' || c.status === 'Interview').length;
    const onboardingPending = candidates.filter(c => c.status === 'Offer Sent');
    const promotionsPending = candidates.filter(c => c.status === 'Pending').length;

    const handleInvite = async (e) => {
        e.preventDefault();
        const today = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const newInvite = {
            id: Date.now(),
            name: inviteEmail.split('@')[0],
            email: inviteEmail,
            role: inviteRole,
            status: 'Screening',
            appliedDate: today,
        };
        setCandidates(prev => [newInvite, ...prev]);
        setInviteEmail('');
        setInviteRole('');
        try {
            await hrAPI.createCandidate(newInvite);
        } catch (err) {
            console.error('Failed to save invitation:', err);
        }
    };


    return (
        <div>
            {/* Stats */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Users size={24} />} value={totalEmployees} label="Total Employees" color="blue" delay={0} />
                <StatsCard icon={<Mail size={24} />} value={pendingInvitations} label="Pending Invitations" color="orange" delay={0.08} />
                <StatsCard icon={<UserPlus size={24} />} value={candidates.filter(c => c.status === 'Hired').length} label="Total Hired" color="green" delay={0.16} />
                <StatsCard icon={<Award size={24} />} value={promotionsPending} label="Promotions Pending" color="red" delay={0.24} />
            </div>

            <div className="grid-2 mb-lg">
                {/* Invite Section */}
                <AnimatedCard delay={0.3}>
                    <div className="card-header">
                        <span className="card-title">Invite New Employee</span>
                    </div>
                    <div className="card-body">
                        <form onSubmit={handleInvite}>
                            <div className="form-group">
                                <input
                                    className="form-input"
                                    type="email"
                                    placeholder="Employee Email"
                                    value={inviteEmail}
                                    onChange={e => setInviteEmail(e.target.value)}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <select className="form-select" value={inviteRole} onChange={e => setInviteRole(e.target.value)} required>
                                    <option value="">Assign Role</option>
                                    <option value="Developer">Developer</option>
                                    <option value="Scrum Master">Scrum Master</option>
                                    <option value="QA Tester">QA Tester</option>
                                    <option value="Designer">Designer</option>
                                    <option value="DevOps">DevOps</option>
                                    <option value="PM">Sprint Master</option>
                                </select>
                            </div>
                            <button className="btn btn-primary w-full" type="submit">
                                <Send size={16} /> Send Invitation
                            </button>
                        </form>
                    </div>
                </AnimatedCard>

                {/* Recent Invitations */}
                <AnimatedCard delay={0.38}>
                    <div className="card-header">
                        <span className="card-title">Recent Invitations</span>
                        <span className="badge badge-neutral">Today</span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Email</th>
                                    <th>Role</th>
                                    <th>Sent</th>
                                </tr>
                            </thead>
                            <tbody>
                                {recentInvitations.map(inv => (
                                    <tr key={inv.id}>
                                        <td style={{ fontWeight: 600 }}>{inv.name}</td>
                                        <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{inv.email}</td>
                                        <td>{inv.role}</td>
                                        <td>
                                            <span className={`badge ${inv.status === 'Today' ? 'badge-info' : 'badge-warning'}`}>
                                                {inv.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </AnimatedCard>
            </div>

            <div className="grid-2">
                {/* Onboarding Pending */}
                <AnimatedCard delay={0.46}>
                    <div className="card-header">
                        <span className="card-title">Onboarding Pending</span>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <span className="badge badge-neutral">Sent Date</span>
                        </div>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table">
                            <tbody>
                                {onboardingPending.map(person => (
                                    <tr key={person.id}>
                                        <td>
                                            <div style={{ fontWeight: 600 }}>{person.name}</div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{person.email}</div>
                                        </td>
                                        <td>{person.role}</td>
                                        <td style={{ color: 'var(--text-secondary)' }}>{person.date}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </AnimatedCard>

                {/* Reports & Insights */}
                <AnimatedCard delay={0.54}>
                    <div className="card-header">
                        <span className="card-title">Reports & Insights</span>
                        <span className="badge badge-neutral">Last 4 Weeks</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={weeklyData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip />
                                    <Legend />
                                    <Bar dataKey="hires" fill="#3b82f6" radius={[4, 4, 0, 0]} name="New Hires" />
                                    <Bar dataKey="departures" fill="#ef4444" radius={[4, 4, 0, 0]} name="Departures" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>
        </div>
    );
}
