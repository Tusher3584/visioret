import { motion, useReducedMotion } from "framer-motion";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Header } from "./components/layout/Header";
import { AdminPage } from "./pages/AdminPage";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { MetricsPage } from "./pages/MetricsPage";
import { PredictPage } from "./pages/PredictPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ScanDetailPage } from "./pages/ScanDetailPage";

function AnimatedRoutes() {
  const location = useLocation();
  const reduceMotion = useReducedMotion();

  // Entrance only, deliberately without AnimatePresence. `mode="wait"` holds
  // the incoming route until the outgoing one finishes animating out -- and
  // since requestAnimationFrame is throttled in background tabs, that exit can
  // simply never complete, leaving the URL changed but the old page still on
  // screen. Navigation must not depend on an animation finishing. Keying on
  // pathname still gives each page its fade-in.
  return (
      <motion.div
        key={location.pathname}
        initial={reduceMotion ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
      >
        <Routes location={location}>
          <Route path="/" element={<PredictPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/scans/:scanId" element={<ScanDetailPage />} />
          <Route path="/metrics" element={<MetricsPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </motion.div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
        <div className="min-h-screen bg-canvas text-ink">
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-[3px] focus:bg-accent focus:px-3 focus:py-2 focus:text-sm focus:text-accent-ink"
          >
            Skip to content
          </a>
          <Header />
          <main id="main" className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8">
            <AnimatedRoutes />
          </main>
        </div>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
