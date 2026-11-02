import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { homepageAPI } from '../services/api';
import {
    MapPin, Star, Calendar, ArrowRight, Users, Shield, Zap,
    BarChart3, Globe, Building2, LogIn, Menu, X, Rocket, Clock,
    CheckCircle, Share2, Sparkles, FileText, Lock, ChevronRight, ChevronLeft
} from 'lucide-react';

/* ── 10 Feature Cards matching jeera.png layout with Web Images ── */
const features = [
    {
        num: '01',
        title: 'Custom Workspace',
        desc: 'Describe how you work, and shape the board, fields, and views around it. Built for any kind of work, not only what comes out of the box.',
        imageUrl: '/features/01-workspace.jpg',
        badge: 'Workspace',
    },
    {
        num: '02',
        title: 'Sprint Planning',
        desc: 'Turn sprint goals into a hybrid human-agent execution loop with real-time velocity tracking and automated story allocation.',
        imageUrl: '/features/02-sprint-planning.jpg',
        hasShare: true,
        badge: 'Agile Board',
    },
    {
        num: '03',
        title: 'Product Roadmap',
        desc: 'Initiatives laid across quarters, grouped by team or theme with multi-team dependency tracking and critical path highlighting.',
        imageUrl: '/features/03-roadmap.jpg',
        badge: 'Roadmap',
    },
    {
        num: '04',
        title: 'Bug Tracker',
        desc: 'Severity, reproduction steps, error logs, and verification status in one clean, prioritized triage and resolution queue.',
        imageUrl: '/features/04-bug-tracker.jpg',
        badge: 'Quality QA',
    },
    {
        num: '05',
        title: 'Content & Release Calendar',
        desc: 'Every milestone, scheduled deploy, and release freeze date color-coded by channel, environment, and tier.',
        imageUrl: '/features/05-release-calendar.jpg',
        badge: 'Releases',
    },
    {
        num: '06',
        title: 'Sales & Delivery Pipeline',
        desc: 'Leads and feature branches staged as a funnel with value, cycle time, and throughput tracked at every milestone.',
        imageUrl: '/features/06-pipeline-funnel.jpg',
        badge: 'Funnel',
    },
    {
        num: '07',
        title: 'OKR Tracker',
        desc: 'One objective, a few key results, and delivery progress rolled up automatically from completed developer and sprint tasks.',
        imageUrl: '/features/07-okr-tracker.jpg',
        badge: 'Objectives',
    },
    {
        num: '08',
        title: 'Event & Milestone Planning',
        desc: 'Checklists, tech summits, demo days, and townhall details all in one shared organizational calendar before launch.',
        imageUrl: '/features/08-event-planning.jpg',
        badge: 'Events',
    },
    {
        num: '09',
        title: 'Hiring Pipeline',
        desc: 'Candidates moving through interview stages, technical evaluation, take-home reviews, ending in an executive offer.',
        imageUrl: '/features/09-hiring-pipeline.jpg',
        badge: 'Talent HR',
    },
    {
        num: '10',
        title: 'Client & Dev Onboarding',
        desc: 'A fixed sequence of setup steps, repo access tokens, and starter PRs so nothing gets skipped during team expansion.',
        imageUrl: '/features/10-dev-onboarding.jpg',
        badge: 'Onboarding',
    },
];

const events = [
    { title: 'Karnataka Cultural Festival & Folk Gala', date: 'Dec 20, 2025', location: 'Bengaluru HQ (Whitefield)', color: '#2563eb' },
    { title: 'Annual Tech Summit 2026', date: 'Jan 15, 2026', location: 'Bengaluru HQ (Whitefield)', color: '#7c3aed' },
    { title: 'Karnataka Innovation Sprint & Hackathon', date: 'Feb 01, 2026', location: 'Bengaluru Campus (Whitefield)', color: '#10b981' },
    { title: 'Executive Leadership Workshop', date: 'Nov 10, 2025', location: 'Whitefield Campus', color: '#f59e0b' },
];

const branches = [
    {
        city: 'Bengaluru',
        type: 'Headquarters',
        employees: 580,
        address: 'ITPB, Whitefield',
        images: ['/branches/bengaluru-1.jpg', '/branches/bengaluru-2.jpg'],
    },
    {
        city: 'Hyderabad',
        type: 'Technology Center',
        employees: 380,
        address: 'HITEC City, Madhapur',
        images: ['/branches/hyderabad-1.jpg', '/branches/hyderabad-2.jpg'],
    },
    {
        city: 'Mumbai',
        type: 'Regional Office',
        employees: 180,
        address: 'BKC, Bandra East',
        images: ['/branches/mumbai-1.jpg', '/branches/mumbai-2.jpg'],
    },
    {
        city: 'Delhi NCR',
        type: 'Regional Office',
        employees: 150,
        address: 'Cyber City, Gurgaon',
        images: ['/branches/delhi-1.jpg', '/branches/delhi-2.jpg'],
    },
    {
        city: 'Pune',
        type: 'Development Center',
        employees: 200,
        address: 'Hinjewadi IT Park',
        images: ['/branches/pune-1.jpg', '/branches/pune-2.jpg'],
    },
    {
        city: 'Chennai',
        type: 'Support Center',
        employees: 120,
        address: 'Tidel Park, Taramani',
        images: ['/branches/chennai-1.jpg', '/branches/chennai-2.jpg'],
    },
];

const workspaceCategories = [
    {
        title: 'Modern Workspaces',
        subtitle: 'Ergonomic Desks & Focus Pods',
        badge: 'Agile Office',
        images: [
            '/workspaces/modern-1.jpg',
            '/workspaces/modern-2.jpg',
            '/workspaces/modern-3.jpg',
        ],
    },
    {
        title: 'Collaboration Zones',
        subtitle: 'Breakout Lounges & Brainstorming',
        badge: 'Team Sync',
        images: [
            '/workspaces/collab-1.jpg',
            '/workspaces/collab-2.jpg',
            '/workspaces/collab-3.jpg',
        ],
    },
    {
        title: 'Innovation Labs',
        subtitle: 'High-Tech Multi-Screen R&D',
        badge: 'Engineering',
        images: [
            '/workspaces/innov-1.jpg',
            '/workspaces/innov-2.jpg',
            '/workspaces/innov-3.jpg',
        ],
    },
    {
        title: 'Training Centers',
        subtitle: 'Interactive Auditoriums & Workshops',
        badge: 'Learning Hub',
        images: [
            '/workspaces/training-1.jpg',
            '/workspaces/training-2.jpg',
            '/workspaces/training-3.jpg',
        ],
    },
];

function WorkspaceSliderCard({ item, index }) {
    const [current, setCurrent] = useState(0);
    const [isPaused, setIsPaused] = useState(false);

    useEffect(() => {
        if (isPaused) return;
        const timer = setInterval(() => {
            setCurrent((prev) => (prev + 1) % item.images.length);
        }, 3400 + index * 350);
        return () => clearInterval(timer);
    }, [isPaused, item.images.length, index]);

    const prevSlide = (e) => {
        e.stopPropagation();
        setCurrent((prev) => (prev - 1 + item.images.length) % item.images.length);
    };

    const nextSlide = (e) => {
        e.stopPropagation();
        setCurrent((prev) => (prev + 1) % item.images.length);
    };

    return (
        <div
            className="home-workspace-card"
            style={{ animationDelay: `${index * 0.1}s` }}
            onMouseEnter={() => setIsPaused(true)}
            onMouseLeave={() => setIsPaused(false)}
        >
            <div className="home-workspace-slider-wrap">
                {item.images.map((src, imgIdx) => (
                    <img
                        key={imgIdx}
                        src={src}
                        alt={`${item.title} ${imgIdx + 1}`}
                        className={`home-workspace-slide-img ${current === imgIdx ? 'active' : ''}`}
                        loading="lazy"
                    />
                ))}
                <div className="home-workspace-overlay" />

                {/* Top Badge & Counter */}
                <div className="home-workspace-top-bar">
                    <span className="home-workspace-badge">{item.badge}</span>
                    <span className="home-workspace-counter">
                        {current + 1} / {item.images.length}
                    </span>
                </div>

                {/* Manual Navigation Arrows */}
                <button
                    type="button"
                    className="home-workspace-nav-btn prev"
                    onClick={prevSlide}
                    aria-label="Previous slide"
                >
                    <ChevronLeft size={16} />
                </button>
                <button
                    type="button"
                    className="home-workspace-nav-btn next"
                    onClick={nextSlide}
                    aria-label="Next slide"
                >
                    <ChevronRight size={16} />
                </button>

                {/* Interactive Dots */}
                <div className="home-workspace-dots">
                    {item.images.map((_, dotIdx) => (
                        <button
                            key={dotIdx}
                            type="button"
                            className={`home-workspace-dot ${current === dotIdx ? 'active' : ''}`}
                            onClick={(e) => {
                                e.stopPropagation();
                                setCurrent(dotIdx);
                            }}
                            aria-label={`Go to slide ${dotIdx + 1}`}
                        />
                    ))}
                </div>
            </div>

            {/* Bottom Content Bar */}
            <div className="home-workspace-info">
                <div className="home-workspace-title">{item.title}</div>
                <div className="home-workspace-sub">{item.subtitle}</div>
            </div>
        </div>
    );
}

const companyEventsCategories = [
    {
        title: 'Annual Tech Summit 2026',
        subtitle: 'Keynotes, System Scale & Panels',
        badge: 'Engineering',
        images: [
            '/events/tech-summit.jpg',
            '/events/tech-1.jpg',
            '/events/tech-2.jpg',
        ],
    },
    {
        title: 'Innovation Hackathon',
        subtitle: '48h Sprint & Prototype Finals',
        badge: 'Hackathon',
        images: [
            '/events/hackathon.jpg',
            '/events/hackathon-1.jpg',
            '/events/hackathon-2.jpg',
        ],
    },
    {
        title: 'Leadership Strategy Offsite',
        subtitle: 'Executive Roadmaps & Alignment',
        badge: 'Leadership',
        images: [
            '/events/team-building.jpg',
            '/events/lead-1.jpg',
            '/events/lead-2.jpg',
        ],
    },
    {
        title: 'Annual Excellence Awards',
        subtitle: 'Star Performers & Team Trophies',
        badge: 'Recognition',
        images: [
            '/events/award-ceremony.jpg',
            '/events/awards-1.jpg',
            '/events/awards-2.jpg',
        ],
    },
    {
        title: 'Sports & Fitness Carnival',
        subtitle: 'Cricket Cup, Relays & Games',
        badge: 'Wellness',
        images: [
            '/events/sports-day.jpg',
            '/events/sports-1.jpg',
            '/events/sports-2.jpg',
        ],
    },
    {
        title: 'Product Demo & Showcase',
        subtitle: 'Sprint Milestones & Live Demos',
        badge: 'Product Launch',
        images: [
            '/events/demo-1.jpg',
            '/events/demo-2.jpg',
            '/events/cultural-night.jpg',
        ],
    },
];

const culturalCategories = [
    {
        title: 'Yakshagana Dance Fest',
        subtitle: 'Coastal Folk Theater & Lore',
        badge: 'Folk Theater',
        images: [
            '/events/yakshagana.jpg',
            '/events/yakshagana-2.jpg',
            '/events/yakshagana-3.jpg',
        ],
    },
    {
        title: 'Mysore Dasara Gala',
        subtitle: 'Illuminated Palace & Royal Utsav',
        badge: 'Royal Heritage',
        images: [
            '/events/mysore-palace.jpg',
            '/events/mysore-1.jpg',
            '/events/mysore-2.jpg',
        ],
    },
    {
        title: 'Dollu Kunitha Folk Art',
        subtitle: 'Traditional Drum Beats & Dance',
        badge: 'Folk Percussion',
        images: [
            '/events/dollu-kunitha.jpg',
            '/events/dollu-1.jpg',
            '/events/dollu-3.jpg',
        ],
    },
    {
        title: 'Hampi Heritage Summit',
        subtitle: 'UNESCO Stone Chariot & Ruins',
        badge: 'World Heritage',
        images: [
            '/events/hampi.jpg',
            '/events/hampi-1.jpg',
            '/events/hampi-2.jpg',
        ],
    },
    {
        title: 'Kambala Cultural Night',
        subtitle: 'Traditional Coastal Buffalo Race',
        badge: 'Folk Sport',
        images: [
            '/events/kambala.jpg',
            '/events/kambala-1.jpg',
            '/events/kambala-3.jpg',
        ],
    },
    {
        title: 'Karnataka Rajyotsava Gala',
        subtitle: 'State Celebration & Folk Music',
        badge: 'State Festival',
        images: [
            '/events/rajyotsava-2.jpg',
            '/events/rajyotsava-3.jpg',
            '/events/cultural-night.jpg',
        ],
    },
];

const teamMembers = [
    {
        name: 'Mallikarjun',
        role: 'Full-Stack Lead & Platform Architect',
        tag: 'Core Platform',
        bio: 'Spearheading core architecture, scalable distributed microservices, and enterprise execution workflows.',
        image: '/team/mallikarjun.png',
        skills: ['React', 'FastAPI', 'System Architecture', 'Agile Workflows'],
    },
    {
        name: 'Mounesh S.D',
        role: 'Backend & Data Infrastructure Lead',
        tag: 'Data & Cloud',
        bio: 'Leading high-throughput telemetry pipelines, database optimization, and secure role-based access.',
        image: '/team/mounesh.png',
        skills: ['Python', 'PostgreSQL', 'MongoDB', 'Cloud Ops'],
    },
    {
        name: 'Shreyas K.T',
        role: 'Frontend Architect & UI/UX Specialist',
        tag: 'UI/UX Design',
        bio: 'Crafting responsive execution dashboards, micro-interactions, and visual interactive boards.',
        image: '/team/shreyas.png',
        skills: ['React', 'CSS Architecture', 'UI/UX Design', 'Performance'],
    },
    {
        name: 'Sumitkumar Hosalli',
        role: 'AI/ML & Agentic Systems Engineer',
        tag: 'AIML & Decision AI',
        bio: 'Architecting LLM pipelines, autonomous reasoning agents, predictive overtime analytics, and smart telemetry.',
        image: '/team/sumit.png',
        skills: ['PyTorch', 'Agentic AI', 'LangChain', 'FastAPI', 'FARM Stack'],
        links: {
            github: 'https://github.com/sumithosalli',
            linkedin: 'https://www.linkedin.com/in/sumitkumar-hosalli',
            portfolio: 'https://sumitkumar-portfolio-kohl.vercel.app',
        },
    },
];

function EventSliderCard({ item, index, badgeColor = '#38bdf8' }) {
    const [current, setCurrent] = useState(0);
    const [isPaused, setIsPaused] = useState(false);

    useEffect(() => {
        if (isPaused || !item.images || item.images.length <= 1) return;
        const timer = setInterval(() => {
            setCurrent((prev) => (prev + 1) % item.images.length);
        }, 3200 + index * 300);
        return () => clearInterval(timer);
    }, [isPaused, item.images, index]);

    const prevSlide = (e) => {
        e.stopPropagation();
        setCurrent((prev) => (prev - 1 + item.images.length) % item.images.length);
    };

    const nextSlide = (e) => {
        e.stopPropagation();
        setCurrent((prev) => (prev + 1) % item.images.length);
    };

    return (
        <div
            className="home-cultural-card"
            style={{ animationDelay: `${index * 0.08}s` }}
            onMouseEnter={() => setIsPaused(true)}
            onMouseLeave={() => setIsPaused(false)}
        >
            <div className="home-cultural-slider-wrap">
                {item.images.map((src, imgIdx) => (
                    <img
                        key={imgIdx}
                        src={src}
                        alt={`${item.title} ${imgIdx + 1}`}
                        className={`home-cultural-slide-img ${current === imgIdx ? 'active' : ''}`}
                        loading="lazy"
                    />
                ))}
                <div className="home-cultural-overlay" />

                {/* Top Badge & Counter */}
                <div className="home-cultural-top-bar">
                    <span className="home-cultural-badge" style={{ color: badgeColor, borderColor: `${badgeColor}55` }}>
                        {item.badge}
                    </span>
                    <span className="home-cultural-counter">
                        {current + 1} / {item.images.length}
                    </span>
                </div>

                {/* Manual Navigation Controls */}
                <button
                    type="button"
                    className="home-cultural-nav-btn prev"
                    onClick={prevSlide}
                    aria-label="Previous slide"
                >
                    <ChevronLeft size={15} />
                </button>
                <button
                    type="button"
                    className="home-cultural-nav-btn next"
                    onClick={nextSlide}
                    aria-label="Next slide"
                >
                    <ChevronRight size={15} />
                </button>

                {/* Interactive Dots */}
                <div className="home-cultural-dots">
                    {item.images.map((_, dotIdx) => (
                        <button
                            key={dotIdx}
                            type="button"
                            className={`home-cultural-dot ${current === dotIdx ? 'active' : ''}`}
                            onClick={(e) => {
                                e.stopPropagation();
                                setCurrent(dotIdx);
                            }}
                            aria-label={`Slide ${dotIdx + 1}`}
                        />
                    ))}
                </div>
            </div>

            {/* Bottom Content / Info Bar */}
            <div className="home-cultural-info">
                <div className="home-cultural-title">{item.title}</div>
                <div className="home-cultural-sub">{item.subtitle}</div>
            </div>
        </div>
    );
}

function BranchSliderCard({ branch, index }) {
    const [current, setCurrent] = useState(0);
    const [isPaused, setIsPaused] = useState(false);

    useEffect(() => {
        if (isPaused || !branch.images || branch.images.length <= 1) return;
        const timer = setInterval(() => {
            setCurrent((prev) => (prev + 1) % branch.images.length);
        }, 3600 + index * 400);
        return () => clearInterval(timer);
    }, [isPaused, branch.images, index]);

    const prevSlide = (e) => {
        e.stopPropagation();
        setCurrent((prev) => (prev - 1 + branch.images.length) % branch.images.length);
    };

    const nextSlide = (e) => {
        e.stopPropagation();
        setCurrent((prev) => (prev + 1) % branch.images.length);
    };

    const isHQ = branch.type === 'Headquarters';

    return (
        <div
            className={`home-branch-card ${isHQ ? 'hq-branch-card' : ''}`}
            style={{ animationDelay: `${index * 0.08}s` }}
            onMouseEnter={() => setIsPaused(true)}
            onMouseLeave={() => setIsPaused(false)}
        >
            {/* Slider with Auto and Manual Slide */}
            <div className="home-branch-slider-wrap">
                {branch.images && branch.images.map((src, imgIdx) => (
                    <img
                        key={imgIdx}
                        src={src}
                        alt={`${branch.city} Office ${imgIdx + 1}`}
                        className={`home-branch-slide-img ${current === imgIdx ? 'active' : ''}`}
                        loading="lazy"
                    />
                ))}
                <div className="home-branch-img-overlay" />

                {/* Top Badge & Image Counter */}
                <div className="home-branch-img-top">
                    <span className={`home-branch-badge ${isHQ ? 'hq' : ''}`}>
                        {isHQ ? '⭐ Headquarters' : branch.type}
                    </span>
                    {branch.images && branch.images.length > 1 && (
                        <span className="home-branch-img-counter">
                            {current + 1} / {branch.images.length}
                        </span>
                    )}
                </div>

                {/* Manual Navigation Controls */}
                {branch.images && branch.images.length > 1 && (
                    <>
                        <button
                            type="button"
                            className="home-branch-nav-btn prev"
                            onClick={prevSlide}
                            aria-label="Previous photo"
                        >
                            <ChevronLeft size={15} />
                        </button>
                        <button
                            type="button"
                            className="home-branch-nav-btn next"
                            onClick={nextSlide}
                            aria-label="Next photo"
                        >
                            <ChevronRight size={15} />
                        </button>
                        <div className="home-branch-dots">
                            {branch.images.map((_, dotIdx) => (
                                <button
                                    key={dotIdx}
                                    type="button"
                                    className={`home-branch-dot ${current === dotIdx ? 'active' : ''}`}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setCurrent(dotIdx);
                                    }}
                                    aria-label={`Slide ${dotIdx + 1}`}
                                />
                            ))}
                        </div>
                    </>
                )}
            </div>

            {/* Content Body */}
            <div className="home-branch-body">
                <div className="home-branch-header">
                    <div className="home-branch-pin">
                        <MapPin size={18} />
                    </div>
                    <div>
                        <div className="home-branch-city">
                            {branch.city}
                            {isHQ && <span className="home-hq-pill">Primary HQ</span>}
                        </div>
                        <div className="home-branch-type-label">{branch.type}</div>
                    </div>
                </div>
                <div className="home-branch-details">
                    <span className="home-branch-address">{branch.address}</span>
                    <span className="home-branch-emp">{branch.employees} employees</span>
                </div>
            </div>
        </div>
    );
}

export default function HomePage() {
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const [termsModalOpen, setTermsModalOpen] = useState(false);
    const [privacyModalOpen, setPrivacyModalOpen] = useState(false);
    const [activeShareIndex, setActiveShareIndex] = useState(null);
    const [dynamicData, setDynamicData] = useState(null);

    useEffect(() => {
        homepageAPI.getData().then((res) => {
            if (res && res.type === 'homepage_data') {
                setDynamicData(res);
            }
        }).catch(() => {});
    }, []);

    const displayFeatures = dynamicData?.features || features;
    const displayEvents = dynamicData?.events || events;
    const displayBranches = dynamicData?.branches || branches;
    const displayWorkspaceCategories = dynamicData?.workspaceCategories || workspaceCategories;
    const displayCompanyEventsCategories = dynamicData?.companyEventsCategories || companyEventsCategories;
    const displayCulturalCategories = dynamicData?.culturalCategories || culturalCategories;
    const displayTeamMembers = dynamicData?.teamMembers || teamMembers;

    return (
        <div className="home-page">
            {/* ─── NAVBAR ─── */}
            <nav className="home-navbar">
                <div className="home-navbar-inner">
                    {/* Left: Styled Logo */}
                    <Link to="/" className="home-navbar-logo">
                        <img src="/logo.jpeg" alt="Samanvaya" className="home-navbar-logo-img" />
                        <div className="home-navbar-logo-text">
                            <span className="home-navbar-logo-sub">Execution Platform</span>
                            <span className="home-navbar-logo-name">Samanvaya</span>
                        </div>
                    </Link>

                    {/* Right: Nav links + Login button */}
                    <div className={`home-navbar-right ${mobileMenuOpen ? 'open' : ''}`}>
                        <a href="#features" className="home-navbar-link" onClick={() => setMobileMenuOpen(false)}>Features</a>
                        <a href="#campus" className="home-navbar-link" onClick={() => setMobileMenuOpen(false)}>Workspaces</a>
                        <a href="#events" className="home-navbar-link" onClick={() => setMobileMenuOpen(false)}>Events</a>
                        <a href="#branches" className="home-navbar-link" onClick={() => setMobileMenuOpen(false)}>Branches</a>
                        <a href="#team" className="home-navbar-link" onClick={() => setMobileMenuOpen(false)}>Team</a>
                        <button
                            type="button"
                            className="home-navbar-link"
                            style={{ background: 'none', border: 'none', cursor: 'pointer', font: 'inherit' }}
                            onClick={() => {
                                setTermsModalOpen(true);
                                setMobileMenuOpen(false);
                            }}
                        >
                            Terms
                        </button>
                        <Link to="/login" className="home-navbar-login-btn" onClick={() => setMobileMenuOpen(false)}>
                            <LogIn size={16} />
                            <span>Login</span>
                        </Link>
                    </div>

                    {/* Mobile menu toggle */}
                    <button className="home-navbar-toggle" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
                        {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
                    </button>
                </div>
            </nav>

            {/* ─── HERO SECTION ─── */}
            <section className="home-hero">
                <div className="home-hero-decorations">
                    <div className="hero-particle hero-particle-1"></div>
                    <div className="hero-particle hero-particle-2"></div>
                    <div className="hero-particle hero-particle-3"></div>
                    <div className="hero-ring hero-ring-1"></div>
                    <div className="hero-ring hero-ring-2"></div>
                </div>

                <div className="home-hero-center">
                    <div className="home-hero-pill">
                        <Rocket size={14} />
                        <span>Overtime Evaluation Platform — Built for Modern Teams</span>
                    </div>

                    <h1 className="home-hero-heading">
                        Smart Overtime<br />
                        <span className="home-hero-accent">Tracking & Evaluation</span>
                    </h1>

                    <p className="home-hero-desc">
                        Samanvaya streamlines how organizations <strong>track, evaluate, and optimize execution</strong> across
                        every department. From real-time engineering analytics to intelligent approval workflows
                        — empower your managers with data-driven decisions and give employees transparent visibility
                        into their contributions.
                    </p>

                    <div className="home-hero-highlights">
                        <div className="home-hero-highlight">
                            <Clock size={16} />
                            <span>Real-Time Hour Tracking</span>
                        </div>
                        <div className="home-hero-highlight">
                            <Shield size={16} />
                            <span>Role-Based Access Control</span>
                        </div>
                        <div className="home-hero-highlight">
                            <CheckCircle size={16} />
                            <span>Automated Approvals</span>
                        </div>
                    </div>

                    <div className="home-hero-cta">
                        <Link to="/login" className="home-hero-cta-btn">
                            <LogIn size={18} />
                            <span>Get Started — Sign In</span>
                        </Link>
                        <a href="#features" className="home-hero-cta-secondary">
                            Explore Features
                            <ArrowRight size={16} />
                        </a>
                    </div>

                    <div className="home-hero-stats">
                        <div className="home-hero-stat"><span className="home-stat-value">1,420</span><span className="home-stat-label">Employees</span></div>
                        <div className="home-hero-stat"><span className="home-stat-value">6</span><span className="home-stat-label">Offices</span></div>
                        <div className="home-hero-stat"><span className="home-stat-value">99.9%</span><span className="home-stat-label">Uptime</span></div>
                        <div className="home-hero-stat"><span className="home-stat-value">50+</span><span className="home-stat-label">Active Sprints</span></div>
                    </div>
                </div>
            </section>

            {/* ─── FEATURES (JEERA STYLE VISUAL CARDS RENDERING WEB IMAGES) ─── */}
            <section className="home-section" id="features">
                <div style={{ textAlign: 'center', marginBottom: 44 }}>
                    <div className="home-features-pill">
                        <Sparkles size={14} />
                        <span>Interactive Visual Workspace</span>
                    </div>
                    <h2 className="home-section-title">Platform Features</h2>
                    <p className="home-section-subtitle">
                        Ten visual power tools built right into Samanvaya to align planning, delivery, and execution.
                    </p>
                </div>

                <div className="jeera-features-grid">
                    {displayFeatures.map((f, i) => (
                        <div key={i} className="jeera-feature-card" style={{ animationDelay: `${i * 0.05}s` }}>
                            {/* Card Image Container rendering image from web */}
                            <div className="jeera-card-image-wrap">
                                <img
                                    src={f.imageUrl}
                                    alt={f.title}
                                    className="jeera-card-web-img"
                                    loading="lazy"
                                />
                                <div className="jeera-card-overlay"></div>
                                {f.hasShare && (
                                    <button
                                        type="button"
                                        className="jeera-card-share-btn"
                                        title="Share Feature"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setActiveShareIndex(i);
                                            navigator.clipboard?.writeText(window.location.href);
                                            setTimeout(() => setActiveShareIndex(null), 2000);
                                        }}
                                    >
                                        <Share2 size={13} />
                                    </button>
                                )}
                                <span className="jeera-card-badge">
                                    {activeShareIndex === i ? 'Link Copied!' : f.badge}
                                </span>
                            </div>

                            {/* Card Content with 01..10 Number, Title, and Description */}
                            <div className="jeera-card-content">
                                <span className="jeera-card-number">{f.num}</span>
                                <h3 className="jeera-card-title">{f.title}</h3>
                                <p className="jeera-card-desc">{f.desc}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* ─── INSTITUTIONAL IMAGES ─── */}
            <section className="home-section home-section-dark" id="campus">
                <h2 className="home-section-title">Our Workspaces</h2>
                <p className="home-section-subtitle">State-of-the-art facilities designed for collaboration and innovation</p>
                <div className="home-image-grid">
                    {displayWorkspaceCategories.map((item, i) => (
                        <WorkspaceSliderCard key={i} item={item} index={i} />
                    ))}
                </div>
            </section>

            {/* ─── EVENT GALLERY ─── */}
            <section className="home-section" id="events">
                <h2 className="home-section-title">Events & Culture</h2>
                <p className="home-section-subtitle">Celebrating milestones and building community together</p>

                {/* Event Schedule */}
                <div className="home-events-list">
                    {displayEvents.map((ev, i) => (
                        <div key={i} className="home-event-item" style={{ animationDelay: `${i * 0.08}s` }}>
                            <div className="home-event-dot" style={{ background: ev.color }}></div>
                            <div className="home-event-info">
                                <div className="home-event-title">{ev.title}</div>
                                <div className="home-event-meta">
                                    <Calendar size={13} /> {ev.date} &nbsp;·&nbsp; <MapPin size={13} /> {ev.location}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* 1. Company Events Gallery */}
                <div style={{ marginTop: 22, marginBottom: 12 }}>
                    <h3 className="home-subsection-title">
                        <Calendar size={18} style={{ color: '#38bdf8' }} />
                        Company Events Gallery
                    </h3>
                </div>
                <div className="home-photo-grid">
                    {displayCompanyEventsCategories.map((item, i) => (
                        <EventSliderCard key={i} item={item} index={i} badgeColor="#38bdf8" />
                    ))}
                </div>

                {/* 2. Karnataka Cultural Heritage Gallery */}
                <div style={{ marginTop: 24, marginBottom: 12 }}>
                    <h3 className="home-subsection-title">
                        <Sparkles size={18} style={{ color: '#f59e0b' }} />
                        Karnataka Cultural Heritage Gallery
                    </h3>
                </div>
                <div className="home-photo-grid">
                    {displayCulturalCategories.map((item, i) => (
                        <EventSliderCard key={i} item={item} index={i} badgeColor="#fbbf24" />
                    ))}
                </div>
            </section>

            {/* ─── BRANCHES ─── */}
            <section className="home-section home-section-dark" id="branches">
                <h2 className="home-section-title">Our Branches</h2>
                <p className="home-section-subtitle">Presence across major cities in India</p>
                {/* Branch Cards with Image Slider & Clean White Aesthetic */}
                <div className="home-branches-grid">
                    {displayBranches.map((b, i) => (
                        <BranchSliderCard key={i} branch={b} index={i} />
                    ))}
                </div>
            </section>

            {/* ─── OUR TEAM ─── */}
            <section className="home-section" id="team">
                <h2 className="home-section-title">Our Team</h2>
                <p className="home-section-subtitle">
                    Meet the engineers and architects driving intelligent execution telemetry and platform innovation
                </p>

                <div className="home-team-grid">
                    {displayTeamMembers.map((member, i) => (
                        <div key={i} className="home-team-card">
                            <div className="home-team-card-glow" />
                            <div className="home-team-avatar-wrapper">
                                <img
                                    src={member.image}
                                    alt={member.name}
                                    className="home-team-avatar-img"
                                    onError={(e) => {
                                        e.currentTarget.onerror = null;
                                        e.currentTarget.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(member.name)}&background=0284c7&color=fff&size=200&bold=true`;
                                    }}
                                />
                                <span className="home-team-tag">{member.tag}</span>
                            </div>
                            <div className="home-team-card-content">
                                <h3 className="home-team-name">{member.name}</h3>
                                <div className="home-team-role">{member.role}</div>
                                <p className="home-team-bio">{member.bio}</p>

                                <div className="home-team-skills">
                                    {member.skills.map((skill, sIdx) => (
                                        <span key={sIdx} className="home-team-skill-pill">
                                            {skill}
                                        </span>
                                    ))}
                                </div>

                                {member.links ? (
                                    <div className="home-team-links">
                                        {member.links.portfolio && (
                                            <a
                                                href={member.links.portfolio}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="home-team-link-btn portfolio"
                                                title="View Portfolio"
                                            >
                                                <Globe size={13} />
                                                <span>Portfolio</span>
                                            </a>
                                        )}
                                        {member.links.github && (
                                            <a
                                                href={member.links.github}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="home-team-link-btn"
                                                title="GitHub Profile"
                                            >
                                                <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                                                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
                                                </svg>
                                                <span>GitHub</span>
                                            </a>
                                        )}
                                        {member.links.linkedin && (
                                            <a
                                                href={member.links.linkedin}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="home-team-link-btn"
                                                title="LinkedIn Profile"
                                            >
                                                <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                                                    <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                                                </svg>
                                                <span>LinkedIn</span>
                                            </a>
                                        )}
                                    </div>
                                ) : (
                                    <div className="home-team-links placeholder">
                                        <span className="home-team-lead-badge">
                                            <Sparkles size={12} /> Core Contributor
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </section>

            {/* ─── COMPACT STREAMLINED FOOTER ─── */}
            <footer className="home-footer">
                <div className="home-footer-grid">
                    {/* Col 1: Brand & Compliance */}
                    <div className="home-footer-brand-col">
                        <div className="home-footer-logo-row">
                            <img src="/logo.jpeg" alt="Samanvaya" className="home-footer-logo-img" />
                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                                <span style={{ fontWeight: 800, fontSize: '1.45rem', color: '#ffffff', letterSpacing: '0.4px', lineHeight: 1.15 }}>Samanvaya</span>
                                <span style={{ fontSize: '0.72rem', color: '#38bdf8', fontWeight: 600, letterSpacing: '0.8px', textTransform: 'uppercase', marginTop: 3 }}>Execution Platform</span>
                            </div>
                        </div>
                        <p className="home-footer-brand-desc">
                            Engineering execution and intelligent overtime telemetry platform built for high-impact teams.
                        </p>
                        <div className="home-footer-compliance-badges">
                            <span className="home-footer-badge">
                                <Shield size={12} /> SOC 2 Type II
                            </span>
                            <span className="home-footer-badge">
                                <Lock size={12} /> ISO 27001
                            </span>
                        </div>
                    </div>

                    {/* Col 2: Navigation */}
                    <div className="home-footer-col">
                        <span className="home-footer-col-title">Navigation</span>
                        <a href="#features" className="home-footer-link">Features</a>
                        <a href="#campus" className="home-footer-link">Workspaces</a>
                        <a href="#events" className="home-footer-link">Events</a>
                        <a href="#branches" className="home-footer-link">Branches</a>
                        <a href="#team" className="home-footer-link">Our Team</a>
                    </div>

                    {/* Col 3: Legal & Governance */}
                    <div className="home-footer-col">
                        <span className="home-footer-col-title">Legal & Security</span>
                        <button
                            type="button"
                            className="home-footer-link"
                            onClick={() => setTermsModalOpen(true)}
                        >
                            <FileText size={14} />
                            <span>Terms & Conditions</span>
                        </button>
                        <button
                            type="button"
                            className="home-footer-link"
                            onClick={() => setPrivacyModalOpen(true)}
                        >
                            <Shield size={14} />
                            <span>Privacy Policy</span>
                        </button>
                        <button
                            type="button"
                            className="home-footer-link"
                            onClick={() => setTermsModalOpen(true)}
                        >
                            <span>Enterprise SLA (99.9%)</span>
                        </button>
                    </div>

                    {/* Col 4: Access & Support */}
                    <div className="home-footer-col">
                        <span className="home-footer-col-title">Access & Support</span>
                        <Link to="/login" className="home-footer-link" style={{ color: '#64b5f6', fontWeight: 600 }}>
                            <LogIn size={14} />
                            <span>Employee Sign In</span>
                        </Link>
                        <span className="home-footer-link" style={{ cursor: 'default' }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block' }}></span>
                            <span>System Status: 99.9%</span>
                        </span>
                        <span className="home-footer-link" style={{ cursor: 'default' }}>
                            <span>support@samanvaya.io</span>
                        </span>
                    </div>
                </div>


                {/* Subfooter */}
                <div className="home-footer-bottom">
                    <div>© 2026 Samanvaya Inc. All rights reserved. &nbsp;·&nbsp; Bengaluru HQ (Whitefield), Karnataka, India &nbsp;·&nbsp; support@samanvaya.io</div>
                    <div className="home-footer-legal-row">
                        <button type="button" className="home-footer-legal-btn" onClick={() => setTermsModalOpen(true)}>
                            Terms & Conditions
                        </button>
                        <span>•</span>
                        <button type="button" className="home-footer-legal-btn" onClick={() => setPrivacyModalOpen(true)}>
                            Privacy Policy
                        </button>
                    </div>
                </div>
            </footer>

            {/* ─── TERMS AND CONDITIONS MODAL ─── */}
            {termsModalOpen && (
                <div className="terms-modal-overlay" onClick={() => setTermsModalOpen(false)}>
                    <div className="terms-modal-box" onClick={(e) => e.stopPropagation()}>
                        <div className="terms-modal-header">
                            <div className="terms-modal-title-group">
                                <div className="terms-modal-icon">
                                    <FileText size={22} />
                                </div>
                                <div>
                                    <h3 className="terms-modal-title">Terms and Conditions</h3>
                                    <div className="terms-modal-sub">Samanvaya Platform Agreement · Version 2.4 · Updated September 2026</div>
                                </div>
                            </div>
                            <button
                                type="button"
                                className="terms-modal-close-btn"
                                onClick={() => setTermsModalOpen(false)}
                                title="Close modal"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="terms-modal-body">
                            <div className="terms-card-block">
                                <div className="terms-block-heading">
                                    <CheckCircle size={16} /> 1. Acceptance of Enterprise Terms
                                </div>
                                <p>
                                    By accessing, deploying, or utilizing the Samanvaya platform ("Service"), your organization and all authorized employee accounts agree to be bound by these Terms and Conditions. These terms apply to all command centers, modules (CEO, HR, Lead, PM, Developer, DevOps, QA), and platform APIs.
                                </p>
                            </div>

                            <div className="terms-card-block">
                                <div className="terms-block-heading">
                                    <Shield size={16} /> 2. Role-Based Access Control & Credential Security
                                </div>
                                <p>
                                    Access is governed by strict organizational credentials and dual-layer verification (Organization Master Key + Employee Authentication). Users may only access modules provisioned to their organizational role. Sharing or delegating Personal Access Tokens (PAT) or credentials violates security compliance.
                                </p>
                            </div>

                            <div className="terms-card-block">
                                <div className="terms-block-heading">
                                    <Clock size={16} /> 3. Overtime Tracking & Contribution Metrics
                                </div>
                                <p>
                                    Samanvaya records work session telemetry, sprint story progress, and review turnaround times for the sole purpose of workload balancing, engineering intelligence, and equitable overtime compensation. All algorithmic evaluations are transparent and auditable by authorized team leads and HR administrators.
                                </p>
                            </div>

                            <div className="terms-card-block">
                                <div className="terms-block-heading">
                                    <Lock size={16} /> 4. Source Code Privacy & Zero-Retention Analysis
                                </div>
                                <p>
                                    Automated code quality evaluation, pull request review scans, and commit velocity calculations occur in transient memory buffers. Samanvaya strictly operates under a Zero-Retention source code policy: your proprietary intellectual property and repository contents are never indexed or used to train third-party public models.
                                </p>
                            </div>

                            <div className="terms-card-block">
                                <div className="terms-block-heading">
                                    <Zap size={16} /> 5. Service Level Agreement (SLA) & 99.9% Uptime
                                </div>
                                <p>
                                    Samanvaya guarantees 99.98% continuous uptime for production workspaces, backed by automated distributed failover, health self-healing routines, and real-time monitoring clusters.
                                </p>
                            </div>

                            <div className="terms-card-block">
                                <div className="terms-block-heading">
                                    <Globe size={16} /> 6. Data Governance, Export & Termination
                                </div>
                                <p>
                                    Your organization retains 100% ownership of all team performance data, audit logs, and project metadata. Upon decommission of a workspace, full JSON/CSV export packages are provided, followed by secure cryptographic data sanitization within 30 days.
                                </p>
                            </div>
                        </div>

                        <div className="terms-modal-footer">
                            <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.45)' }}>
                                Questions regarding these terms? Contact legal@samanvaya.io
                            </span>
                            <button
                                type="button"
                                className="terms-modal-agree-btn"
                                onClick={() => setTermsModalOpen(false)}
                            >
                                <CheckCircle size={16} />
                                <span>I Understand & Agree</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ─── PRIVACY POLICY MODAL ─── */}
            {privacyModalOpen && (
                <div className="terms-modal-overlay" onClick={() => setPrivacyModalOpen(false)}>
                    <div className="terms-modal-box" onClick={(e) => e.stopPropagation()}>
                        <div className="terms-modal-header">
                            <div className="terms-modal-title-group">
                                <div className="terms-modal-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
                                    <Shield size={22} />
                                </div>
                                <div>
                                    <h3 className="terms-modal-title">Privacy Policy</h3>
                                    <div className="terms-modal-sub">Enterprise Data Protection & Security Guidelines · September 2026</div>
                                </div>
                            </div>
                            <button
                                type="button"
                                className="terms-modal-close-btn"
                                onClick={() => setPrivacyModalOpen(false)}
                                title="Close modal"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="terms-modal-body">
                            <div className="terms-card-block">
                                <div className="terms-block-heading" style={{ color: '#10b981' }}>
                                    1. Information Collection & Telemetry
                                </div>
                                <p>
                                    We collect professional organizational identifiers (employee ID, work email, department, role) and technical session tokens required to authenticate and deliver role-specific dashboards.
                                </p>
                            </div>

                            <div className="terms-card-block">
                                <div className="terms-block-heading" style={{ color: '#10b981' }}>
                                    2. Encryption & Key Management
                                </div>
                                <p>
                                    All data in transit is protected using TLS 1.3 encryption. At rest, database records and token hashes are encrypted using AES-256 standard protocols with secure HSM key management.
                                </p>
                            </div>

                            <div className="terms-card-block">
                                <div className="terms-block-heading" style={{ color: '#10b981' }}>
                                    3. No Third-Party Telemetry Sharing
                                </div>
                                <p>
                                    Samanvaya does not sell, license, or share employee performance, overtime records, or organization data with advertisers or third-party data brokers.
                                </p>
                            </div>
                        </div>

                        <div className="terms-modal-footer">
                            <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.45)' }}>
                                Data Protection Officer: privacy@samanvaya.io
                            </span>
                            <button
                                type="button"
                                className="terms-modal-agree-btn"
                                style={{ background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)' }}
                                onClick={() => setPrivacyModalOpen(false)}
                            >
                                <CheckCircle size={16} />
                                <span>Acknowledge & Close</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
