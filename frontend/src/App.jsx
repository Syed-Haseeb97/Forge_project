import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import Dashboard from './pages/Dashboard'
import SubmitReport from './pages/SubmitReport'
import ReportsList from './pages/ReportsList'
import ReportDetail from './pages/ReportDetail'
import AuthPage from './pages/AuthPage'
import AboutPage from './pages/AboutPage'
import PrivacyPage from './pages/PrivacyPage'
import { useTheme } from './components/ThemeContext'
import { useAuth } from './components/AuthContext'

export default function App() {
  const { isDark } = useTheme()
  const { isVerified } = useAuth()
  const location = useLocation()
  const isPublicInfoRoute = location.pathname === '/about' || location.pathname === '/privacy'

  // Allow viewing About and Privacy policies even when not authenticated
  if (!isVerified && isPublicInfoRoute) {
    return (
      <div
        className={`app-container min-h-screen ${isDark ? 'dark' : ''} flex flex-col transition-colors`}
        data-theme={isDark ? 'dark' : 'light'}
      >
        <Navbar />
        <main className="flex-1 w-full">
          <Routes>
            <Route path="/about" element={<AboutPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
          </Routes>
        </main>
        <Footer />
        <Toaster
          position="top-right"
          toastOptions={{
            className: 'text-xs font-semibold bg-white text-[#0d3035] border border-[#173e42]/15 shadow-lg dark:bg-[#0b2529] dark:text-[#f6f4ee] dark:border-[#173e42]/40',
          }}
        />
      </div>
    )
  }

  // Strict Gate: Authentication required first before accessing portal features
  if (!isVerified) {
    return (
      <div
        className={`app-container min-h-screen ${isDark ? 'dark' : ''} flex flex-col transition-colors`}
        data-theme={isDark ? 'dark' : 'light'}
      >
        <AuthPage />
        <Toaster
          position="top-right"
          toastOptions={{
            className: 'text-xs font-semibold bg-white text-[#0d3035] border border-[#173e42]/15 shadow-lg dark:bg-[#0b2529] dark:text-[#f6f4ee] dark:border-[#173e42]/40',
          }}
        />
      </div>
    )
  }

  // Once verified, full portal access is granted
  return (
    <div
      className={`app-container min-h-screen ${isDark ? 'dark' : ''} flex flex-col transition-colors`}
      data-theme={isDark ? 'dark' : 'light'}
    >
      <Navbar />
      <main className="flex-1 w-full">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/submit" element={<SubmitReport />} />
          <Route path="/reports" element={<ReportsList />} />
          <Route path="/reports/:id" element={<ReportDetail />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Footer />
      <Toaster
        position="top-right"
        toastOptions={{
          className: 'text-xs font-semibold bg-white text-[#0d3035] border border-[#173e42]/15 shadow-lg dark:bg-[#0b2529] dark:text-[#f6f4ee] dark:border-[#173e42]/40',
        }}
      />
    </div>
  )
}
