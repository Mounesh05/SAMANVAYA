import LoginPage from './LoginPage';
import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function LoginStandalonePage() {
    const navigate = useNavigate();

    return (
        <div className="login-standalone">
            {/* Animated background rings */}
            <div className="login-bg-rings">
                <div className="login-ring login-ring-1"></div>
                <div className="login-ring login-ring-2"></div>
                <div className="login-ring login-ring-3"></div>
            </div>

            {/* Floating particles decoration */}
            <div className="login-standalone-particles">
                <div className="particle particle-1"></div>
                <div className="particle particle-2"></div>
                <div className="particle particle-3"></div>
                <div className="particle particle-4"></div>
                <div className="particle particle-5"></div>
            </div>

            {/* Back to home */}
            <button className="login-back-btn" onClick={() => navigate('/')}>
                <ArrowLeft size={18} />
                <span>Back to Home</span>
            </button>

            {/* Login card – centered, no logo above */}
            <LoginPage />
        </div>
    );
}
