import AnimatedCard from './AnimatedCard';

export default function StatsCard({ icon, value, label, trend, trendDir, color = 'blue', delay = 0 }) {
    return (
        <AnimatedCard delay={delay} className="stat-card" style={{ border: 'none' }}>
            <div className={`stat-icon ${color}`}>
                {icon}
            </div>
            <div className="stat-info">
                <div className="stat-value">{value}</div>
                <div className="stat-label">{label}</div>
                {trend && (
                    <span className={`stat-trend ${trendDir || 'up'}`}>
                        {trendDir === 'down' ? '↓' : '↑'} {trend}
                    </span>
                )}
            </div>
        </AnimatedCard>
    );
}
