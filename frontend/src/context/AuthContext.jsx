import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI, companiesAPI } from '../services/api';

const AuthContext = createContext(null);

/* ── Company-wide password (same for all employees) ── */
const COMPANY_PASSWORD = 'Samanvaya@org123';

const DEFAULT_COMPANY = {
    id: 'ORG-001',
    code: 'SMV',
    name: 'Samanvaya Inc.',
    domain: 'samanvaya.io',
    industry: 'Enterprise AI & Developer Intelligence',
    location: 'Bengaluru HQ (Whitefield), Karnataka, India',
    employee_count: 580,
    project_count: 6,
    status: 'Active',
    created_by: 'Alexander Sterling (CEO)'
};

/* ── Fallback users for offline/dev mode ── */
const MOCK_USERS = [
    { id: 'EMP-CEO-001', password: 'Emp@ceo123', name: 'Alexander Sterling', role: 'CEO', email: 'ceo@samanvaya.io', dept: 'Executive', avatar: 'AS' },
    { id: 'EMP-HR-001', password: 'Emp@hr123', name: 'Priya Sharma', role: 'HR', email: 'hr@samanvaya.io', dept: 'Human Resources', avatar: 'PS' },
    { id: 'EMP-PM-001', password: 'Emp@pm123', name: 'Rachel Zane', role: 'PM', email: 'pm@samanvaya.io', dept: 'Management', avatar: 'RZ' },
    { id: 'EMP-LEAD-001', password: 'Emp@lead123', name: 'Marcus Vance', role: 'LEAD', email: 'lead@samanvaya.io', dept: 'Engineering', avatar: 'MV' },
    { id: 'EMP-DEV-001', password: 'Emp@dev123', name: 'Sarah Connor', role: 'DEVELOPER', email: 'dev@samanvaya.io', dept: 'Engineering', avatar: 'SC' },
    { id: 'EMP-OPS-001', password: 'Emp@ops123', name: 'Jordan Hayes', role: 'DEVOPS', email: 'ops@samanvaya.io', dept: 'Infrastructure', avatar: 'JH' },
    { id: 'EMP-QA-001', password: 'Emp@qa123', name: 'Elena Rostova', role: 'QA', email: 'qa@samanvaya.io', dept: 'Quality Assurance', avatar: 'ER' },
    { id: 'EMP-CEO-VAL-001', password: 'Emp@ceo123', name: 'Dr. Vikram Malhotra', role: 'CEO', email: 'ceo@valence.io', dept: 'Executive', avatar: 'VM', company_id: 'ORG-004', company_name: 'Valence Autonomous Systems' },
    { id: 'EMP-HR-VAL-001', password: 'Emp@hr123', name: 'Ananya Sen', role: 'HR', email: 'hr@valence.io', dept: 'Human Resources', avatar: 'AS', company_id: 'ORG-004', company_name: 'Valence Autonomous Systems' },
];

const INITIAL_COMPANIES = [
    DEFAULT_COMPANY,
    {
        id: 'ORG-004',
        code: 'VAL',
        name: 'Valence Autonomous Systems',
        domain: 'valence.io',
        industry: 'Autonomous Robotics & AI Control',
        location: 'Bengaluru HQ (Whitefield), Karnataka, India',
        employee_count: 240,
        project_count: 3,
        status: 'Active',
        created_by: 'SuperAdmin (Platform Administrator)',
        assigned_ceo: {
            employee_id: 'EMP-CEO-VAL-001',
            name: 'Dr. Vikram Malhotra',
            email: 'ceo@valence.io',
            phone: '+91 98450 11223'
        },
        assigned_hr: {
            employee_id: 'EMP-HR-VAL-001',
            name: 'Ananya Sen',
            email: 'hr@valence.io',
            phone: '+91 98450 44556'
        }
    }
];

export function AuthProvider({ children }) {
    const [user, setUser] = useState(() => {
        const saved = sessionStorage.getItem('samanvaya_user');
        return saved ? JSON.parse(saved) : null;
    });

    const [companies, setCompanies] = useState([DEFAULT_COMPANY]);
    const [currentCompany, setCurrentCompany] = useState(() => {
        try {
            const savedCo = localStorage.getItem('samanvaya_company');
            return savedCo ? JSON.parse(savedCo) : DEFAULT_COMPANY;
        } catch {
            return DEFAULT_COMPANY;
        }
    });

    const refreshCompanies = async () => {
        try {
            const list = await companiesAPI.getAll();
            if (Array.isArray(list) && list.length > 0) {
                setCompanies(list);
                // If currentCompany is not in the list, update it
                const match = list.find(c => c.id === currentCompany.id || c.code === currentCompany.code);
                if (match) {
                    setCurrentCompany(match);
                    localStorage.setItem('samanvaya_company', JSON.stringify(match));
                }
            }
        } catch (err) {
            console.error('Failed to load companies:', err);
        }
    };

    useEffect(() => {
        refreshCompanies();
    }, []);

    const switchCompany = (coOrId) => {
        let target = coOrId;
        if (typeof coOrId === 'string') {
            target = companies.find(c => c.id === coOrId || c.code === coOrId) || { ...DEFAULT_COMPANY, id: coOrId, name: coOrId };
        }
        setCurrentCompany(target);
        localStorage.setItem('samanvaya_company', JSON.stringify(target));
    };

    const COMPANY_PASSWORDS = ['Samanvaya@org123', 'password123'];

    const login = async (userId, companyPwd, personalPwd) => {
        /* Step 1 – validate company password client-side (or let backend verify) */
        if (companyPwd && !COMPANY_PASSWORDS.includes(companyPwd)) {
            return { success: false, error: 'Invalid company password.' };
        }

        /* Step 2 – call backend API with all fields */
        try {
            const data = await authAPI.login(
                userId.trim(),   // employee_id / email
                companyPwd || 'Samanvaya@org123',
                personalPwd      // password
            );
            if (data && (data.employee_id || data.user || data.token)) {
                const userObj = {
                    ...(data.user || {}),
                    ...(data.employee_id ? data : {}),
                    token: data.token || data.access_token,
                };
                if (!userObj.id) userObj.id = userObj.employee_id;
                setUser(userObj);
                sessionStorage.setItem('samanvaya_user', JSON.stringify(userObj));
                if (data.token) sessionStorage.setItem('token', data.token);
                return { success: true, user: userObj };
            }
            return { success: false, error: 'Invalid credentials.' };
        } catch (err) {
            /* Offline fallback — only used when backend is unreachable */
            console.warn('Backend login failed, falling back to MOCK_USERS:', err.message);
            const found = MOCK_USERS.find(
                u => (u.id.toLowerCase() === userId.trim().toLowerCase() || u.email.toLowerCase() === userId.trim().toLowerCase()) && (u.password === personalPwd || personalPwd === 'password123')
            );
            if (!found) return { success: false, error: 'Invalid User ID or personal password.' };
            const { password: _, ...safeUser } = found;
            setUser(safeUser);
            sessionStorage.setItem('samanvaya_user', JSON.stringify(safeUser));
            return { success: true, user: safeUser };
        }
    };

    const logout = () => {
        setUser(null);
        sessionStorage.removeItem('samanvaya_user');
        sessionStorage.removeItem('token');
    };

    return (
        <AuthContext.Provider value={{
            user,
            login,
            logout,
            isAuthenticated: !!user,
            companies,
            currentCompany,
            switchCompany,
            refreshCompanies
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
}

export { MOCK_USERS, COMPANY_PASSWORD };
