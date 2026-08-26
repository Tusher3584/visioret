import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Header } from "./components/layout/Header";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { MetricsPage } from "./pages/MetricsPage";
import { PredictPage } from "./pages/PredictPage";
import { ScanDetailPage } from "./pages/ScanDetailPage";

function AnimatedRoutes() {
  const location = useLocation();
  const reduceMotion = useReducedMotion();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={reduceMotion ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reduceMotion ? undefined : { opacity: 0 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
      >
        <Routes location={location}>
          <Route path="/" element={<PredictPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/scans/:scanId" element={<ScanDetailPage />} />
          <Route path="/metrics" element={<MetricsPage />} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
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
