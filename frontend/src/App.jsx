import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';

// Pages
import PatientIntake from './pages/PatientIntake';
import EMSView from './pages/EMSView';
import HospitalCommand from './pages/HospitalCommand';
import ClinicianWorkspace from './pages/ClinicianWorkspace';
import ReportDecoder from './components/ReportDecoder';

// Shared ambulance location context
import { AmbulanceLocationProvider } from './context/AmbulanceLocationContext';

import {
  Activity, Bell, UserCircle, Ambulance, Stethoscope,
  ClipboardList, HeartPulse, Map, Menu, X
} from 'lucide-react';

const NAV_ITEMS = [
  { to: '/',          icon: UserCircle,   label: 'Patient Intake',      section: 'field' },
  { to: '/ems',       icon: Ambulance,    label: 'Ambulance',           section: 'field' },
  { to: '/hospital',  icon: Activity,     label: 'Hospital Command',    section: 'hospital' },
  { to: '/clinician', icon: Stethoscope,  label: 'Clinician Review',    section: 'hospital' },
  { to: '/decoder',   icon: ClipboardList,label: 'Report Decoder',      section: 'hospital' },
];

function AppLayout() {
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const handleOnline  = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    window.addEventListener('online',  handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online',  handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const activeTab = location.pathname;

  const NavItem = ({ to, icon: Icon, label }) => {
    const isActive = to === '/'
      ? activeTab === '/'
      : activeTab.startsWith(to);

    return (
      <Link
        to={to}
        onClick={() => setMobileNavOpen(false)}
        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
          isActive
            ? 'bg-rose-50 text-rose-700 border border-rose-100'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }`}
      >
        <Icon size={17} className={isActive ? 'text-rose-600' : 'text-gray-400'} />
        {label}
      </Link>
    );
  };

  const Sidebar = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-gray-100 flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-rose-600 rounded-lg flex items-center justify-center flex-shrink-0">
            <HeartPulse size={18} className="text-white" />
          </div>
          <span className="font-bold text-gray-900 text-lg tracking-tight">MEDOPS</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest px-3 mb-2">Field</p>
        {NAV_ITEMS.filter(n => n.section === 'field').map(item => (
          <NavItem key={item.to} {...item} />
        ))}

        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest px-3 mt-5 mb-2">Hospital</p>
        {NAV_ITEMS.filter(n => n.section === 'hospital').map(item => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>

      {/* Status Footer */}
      <div className="px-4 py-3 border-t border-gray-100">
        <div className="flex items-center gap-2 text-xs">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${isOffline ? 'bg-red-500' : 'bg-emerald-500'}`} />
          <span className="text-gray-500">
            {isOffline ? 'Backend offline' : 'Backend connected'}
          </span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-gray-50 font-sans">

      {/* Desktop Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-white border-r border-gray-200 hidden md:flex flex-col">
        <Sidebar />
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-gray-900/40"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-white shadow-xl flex flex-col">
            <Sidebar />
          </aside>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Top Bar */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 flex-shrink-0 sticky top-0 z-20">
          <button
            className="md:hidden p-1.5 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100"
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu size={20} />
          </button>

          <div className="md:hidden flex items-center gap-2">
            <div className="w-6 h-6 bg-rose-600 rounded-md flex items-center justify-center">
              <HeartPulse size={13} className="text-white" />
            </div>
            <span className="font-bold text-gray-900 text-base">MEDOPS</span>
          </div>

          <div className="hidden md:block" />

          <div className="flex items-center gap-3">
            {isOffline && (
              <span className="text-xs font-medium text-red-600 bg-red-50 border border-red-100 px-2.5 py-1 rounded-full">
                Backend offline
              </span>
            )}
            <button className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 relative" aria-label="Notifications">
              <Bell size={18} />
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto w-full">
            <Routes>
              <Route path="/"          element={<PatientIntake />} />
              <Route path="/ems"       element={<EMSView />} />
              <Route path="/hospital"  element={<HospitalCommand />} />
              <Route path="/clinician" element={<ClinicianWorkspace />} />
              <Route path="/decoder"   element={<ReportDecoder />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AmbulanceLocationProvider>
        <AppLayout />
      </AmbulanceLocationProvider>
    </Router>
  );
}
