import { useLocation } from 'react-router-dom';
import { Construction } from 'lucide-react';

export default function GenericPage() {
    const location = useLocation();
    const name = location.pathname.replace(/^\//, '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

    return (
        <div className="coming-soon">
            <div className="coming-soon-icon">
                <Construction size={36} />
            </div>
            <h2 className="coming-soon-title">{name}</h2>
            <p className="coming-soon-desc">
                This section is under active development and will be available soon.
                Stay tuned for updates!
            </p>
        </div>
    );
}
