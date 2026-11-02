import { useEffect, useRef, useState } from 'react';

export default function AnimatedCard({ children, delay = 0, className = '', style = {} }) {
    const [visible, setVisible] = useState(false);
    const ref = useRef();

    useEffect(() => {
        const timer = setTimeout(() => setVisible(true), 50);
        return () => clearTimeout(timer);
    }, []);

    return (
        <div
            ref={ref}
            className={`card ${className}`}
            style={{
                ...style,
                opacity: visible ? 1 : 0,
                transform: visible ? 'translateY(0)' : 'translateY(30px)',
                transition: `opacity 0.5s ease ${delay}s, transform 0.5s ease ${delay}s`,
            }}
        >
            {children}
        </div>
    );
}
