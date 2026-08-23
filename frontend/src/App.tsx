import { BrowserRouter, Route, Routes } from "react-router-dom";
import ModelMetrics from "./components/ModelMetrics";
import Nav from "./components/Nav";
import ScanDetail from "./components/ScanDetail";
import ScanHistory from "./components/ScanHistory";
import UploadPredict from "./components/UploadPredict";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-50">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 sm:py-10">
          <Nav />
          <main>
            <Routes>
              <Route path="/" element={<UploadPredict />} />
              <Route path="/history" element={<ScanHistory />} />
              <Route path="/scans/:scanId" element={<ScanDetail />} />
              <Route path="/metrics" element={<ModelMetrics />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
