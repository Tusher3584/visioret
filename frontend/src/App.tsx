import { AnimatePresence, motion } from "framer-motion";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import AuthPage from "./components/AuthPage";
import ModelMetrics from "./components/ModelMetrics";
import Nav from "./components/Nav";
import ScanDetail from "./components/ScanDetail";
import ScanHistory from "./components/ScanHistory";
import UploadPredict from "./components/UploadPredict";
import { AuthProvider } from "./context/AuthContext";

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
      >
        <Routes location={location}>
          <Route path="/" element={<UploadPredict />} />
          <Route path="/history" element={<ScanHistory />} />
          <Route path="/scans/:scanId" element={<ScanDetail />} />
          <Route path="/metrics" element={<ModelMetrics />} />
          <Route path="/login" element={<AuthPage />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

function AmbientBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
      <div className="animate-drift-a absolute -left-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-blue-400/20 blur-3xl dark:bg-blue-500/10" />
      <div className="animate-drift-b absolute -right-32 top-1/3 h-[28rem] w-[28rem] rounded-full bg-violet-400/15 blur-3xl dark:bg-violet-500/10" />
      <div className="absolute bottom-0 left-1/4 h-96 w-96 rounded-full bg-emerald-400/10 blur-3xl dark:bg-emerald-500/5" />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="relative min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-50">
          <AmbientBackground />
          <div className="relative mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 sm:py-10">
            <Nav />
            <main>
              <AnimatedRoutes />
            </main>
          </div>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}
