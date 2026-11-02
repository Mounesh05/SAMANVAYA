import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Columns, CheckSquare, Clock, Cpu } from 'lucide-react';
import { devAPI } from '../../services/api';

const columns = ['To Do', 'In Progress', 'In Review', 'Changes Requested', 'Done'];
const colColors = {
    'To Do': { bg: '#f0f2f5', accent: '#6b7280', icon: '📋' },
    'In Progress': { bg: '#eff6ff', accent: '#3b82f6', icon: '🔨' },
    'In Review': { bg: '#fffbeb', accent: '#f59e0b', icon: '👁️' },
    'Changes Requested': { bg: '#fef2f2', accent: '#ef4444', icon: '🔄' },
    'Done': { bg: '#ecfdf5', accent: '#10b981', icon: '✅' },
};
const getColor = (v) => v >= 80 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';
const reviewBadge = {
    Approved: { bg: '#ecfdf5', color: '#10b981' },
    Pending: { bg: '#fffbeb', color: '#f59e0b' },
    'Changes Requested': { bg: '#fef2f2', color: '#ef4444' },
    'In Review': { bg: '#eff6ff', color: '#3b82f6' },
};

export default function DevSprintBoard() {
    const [cards, setCards] = useState([]);
    const [dragId, setDragId] = useState(null);

    useEffect(() => {
        devAPI.sprintBoard().then(data => { if (Array.isArray(data)) setCards(data); }).catch(() => { });
    }, []);

    const handleDragStart = (id) => setDragId(id);
    const handleDrop = (col) => {
        if (!dragId) return;
        setCards(prev => prev.map(c => c.id === dragId ? { ...c, status: col } : c));
        devAPI.updateStory(dragId, { status: col }).catch(err => console.error('Failed to update story status:', err));
        setDragId(null);
    };

    const totalPoints = cards.reduce((a, c) => a + (c.points || 0), 0);
    const donePoints = cards.filter(c => c.status === 'Done').reduce((a, c) => a + (c.points || 0), 0);
    const avgAlignment = cards.length ? Math.round(cards.reduce((a, c) => a + (c.alignment || 0), 0) / cards.length) : 0;
    const currentSprint = cards[0]?.sprint || 'Current Sprint';

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Columns size={24} />} value={cards.length} label="Total Cards" color="blue" delay={0} />
                <StatsCard icon={<CheckSquare size={24} />} value={`${donePoints}/${totalPoints}`} label="Points Done" color="green" delay={0.08} />
                <StatsCard icon={<Cpu size={24} />} value={`${avgAlignment}%`} label="Avg Alignment" color="orange" delay={0.16} />
                <StatsCard icon={<Clock size={24} />} value={currentSprint} label="Current Sprint" color="blue" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Sprint Board — Personal View</span>
                    <span className="badge badge-info">{currentSprint}</span>
                </div>
                <div className="card-body" style={{ padding: 16, overflowX: 'auto' }}>
                    <div style={{ display: 'flex', gap: 14, minWidth: 1100 }}>
                        {columns.map(col => {
                            const colCards = cards.filter(c => c.status === col);
                            const cfg = colColors[col];
                            return (
                                <div key={col}
                                    onDragOver={e => e.preventDefault()}
                                    onDrop={() => handleDrop(col)}
                                    style={{
                                        flex: 1, minWidth: 200, background: cfg.bg,
                                        borderRadius: 'var(--radius-md)', padding: 12,
                                        border: dragId ? `2px dashed ${cfg.accent}40` : '2px solid transparent',
                                        transition: 'border 0.2s ease'
                                    }}>
                                    <div style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                        marginBottom: 12, padding: '0 4px'
                                    }}>
                                        <span style={{ fontWeight: 700, fontSize: '0.82rem', color: cfg.accent }}>
                                            {cfg.icon} {col}
                                        </span>
                                        <span style={{
                                            background: cfg.accent + '20', color: cfg.accent,
                                            padding: '2px 8px', borderRadius: 10,
                                            fontSize: '0.7rem', fontWeight: 700
                                        }}>{colCards.length}</span>
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 120 }}>
                                        {colCards.map(card => (
                                            <div key={card.id}
                                                draggable
                                                onDragStart={() => handleDragStart(card.id)}
                                                style={{
                                                    background: '#fff', borderRadius: 'var(--radius-sm)',
                                                    padding: '12px 14px', boxShadow: 'var(--shadow-sm)',
                                                    border: '1px solid var(--border-light)',
                                                    cursor: 'grab', transition: 'all 0.2s ease',
                                                }}>
                                                <div style={{ fontWeight: 600, fontSize: '0.82rem', marginBottom: 6, lineHeight: 1.4 }}>
                                                    {card.title}
                                                </div>
                                                <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: 8 }}>
                                                    {card.id} · {card.module}
                                                </div>
                                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, flexWrap: 'wrap' }}>
                                                    {/* Story Points */}
                                                    <span style={{
                                                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                                        width: 24, height: 24, borderRadius: '50%',
                                                        background: 'var(--info-bg)', color: 'var(--info)',
                                                        fontWeight: 700, fontSize: '0.72rem'
                                                    }}>{card.points}</span>

                                                    {/* Alignment */}
                                                    <span style={{ fontWeight: 700, fontSize: '0.75rem', color: getColor(card.alignment) }}>
                                                        {card.alignment}%
                                                    </span>

                                                    {/* Reviewer */}
                                                    <span style={{
                                                        fontSize: '0.68rem', fontWeight: 600,
                                                        padding: '2px 8px', borderRadius: 10,
                                                        background: (reviewBadge[card.reviewStatus] || reviewBadge.Pending).bg,
                                                        color: (reviewBadge[card.reviewStatus] || reviewBadge.Pending).color,
                                                    }}>
                                                        {card.reviewStatus}
                                                    </span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
