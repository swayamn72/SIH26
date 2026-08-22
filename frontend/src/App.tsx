import { useState, useEffect } from "react";
import { Routes, Route, NavLink, useNavigate, useLocation } from "react-router-dom";
import { Upload, FileSearch, LayoutDashboard, Search, GitGraph, Shield, Trash2, ChevronDown, Menu, X } from "lucide-react";
import { UploadPage } from "./pages/UploadPage";
import { ExtractionReviewPage } from "./pages/ExtractionReviewPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EvidenceExplorerPage } from "./pages/EvidenceExplorerPage";
import { ProofGraphPage } from "./pages/ProofGraphPage";
import { StatementProvider, useStatement } from "./lib/StatementContext";

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { statements, currentId, currentStatement, setCurrentId, purgeAll } = useStatement();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Close mobile sidebar on page navigation
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  // Close mobile sidebar on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileMenuOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const navItems = [
    { to: "/", label: "Upload & History", icon: Upload, exact: true },
    {
      to: currentId ? `/review/${currentId}` : "/review",
      label: "Extraction Review",
      icon: FileSearch,
      activePath: "/review",
    },
    {
      to: currentId ? `/dashboard/${currentId}` : "/dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
      activePath: "/dashboard",
    },
    {
      to: currentId ? `/evidence/${currentId}` : "/evidence",
      label: "Evidence Explorer",
      icon: Search,
      activePath: "/evidence",
    },
    {
      to: currentId ? `/graph/${currentId}` : "/graph",
      label: "Proof Graph",
      icon: GitGraph,
      activePath: "/graph",
    },
  ];

  const handleSelectStatement = (idStr: string) => {
    const numId = Number(idStr);
    setCurrentId(numId);
    setMobileMenuOpen(false);
    const path = location.pathname;
    if (path.startsWith("/review")) {
      navigate(`/review/${numId}`);
    } else if (path.startsWith("/dashboard")) {
      navigate(`/dashboard/${numId}`);
    } else if (path.startsWith("/evidence")) {
      navigate(`/evidence/${numId}`);
    } else if (path.startsWith("/graph")) {
      navigate(`/graph/${numId}`);
    }
  };

  const handlePurgeAll = async () => {
    if (window.confirm("Are you sure you want to purge all statements and database records?")) {
      await purgeAll();
      setMobileMenuOpen(false);
      navigate("/");
    }
  };

  return (
    <div className="flex flex-col lg:flex-row min-h-screen bg-gray-50 text-gray-900">
      {/* Mobile Top App Bar */}
      <header className="lg:hidden bg-white border-b border-gray-200 px-4 py-2.5 flex items-center justify-between sticky top-0 z-30 shadow-sm">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-blue-600" />
          <span className="font-bold text-base text-gray-900">MuleGuard</span>
          <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded font-mono">Local</span>
        </div>

        <div className="flex items-center gap-2">
          {currentStatement && (
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold truncate max-w-[120px] ${
                currentStatement.tier === "CONFIRMED_SUSPICIOUS"
                  ? "bg-red-100 text-red-700"
                  : currentStatement.tier === "LIKELY_LEGITIMATE"
                  ? "bg-green-100 text-green-700"
                  : currentStatement.tier === "REVIEW_REQUIRED"
                  ? "bg-amber-100 text-amber-700"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              #{currentStatement.id}
            </span>
          )}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:outline-none"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </header>

      {/* Mobile Backdrop Overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 lg:hidden transition-opacity"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar (Desktop Static & Mobile Sliding Drawer) */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 flex flex-col shrink-0 transform transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 ${
          mobileMenuOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full"
        }`}
      >
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Shield className="w-6 h-6 text-blue-600" />
              <span className="font-bold text-lg text-gray-900">MuleGuard</span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">Local v0.1.0 · Offline</p>
          </div>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="lg:hidden p-1 text-gray-400 hover:text-gray-600 rounded-md"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Active Statement Selector in Sidebar */}
        <div className="p-3 border-b border-gray-100 bg-gray-50/50">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1 flex items-center justify-between">
            <span>Active Statement</span>
            {statements.length > 0 && (
              <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                {statements.length} Total
              </span>
            )}
          </div>

          {statements.length > 0 ? (
            <div className="relative">
              <select
                value={currentId || ""}
                onChange={(e) => handleSelectStatement(e.target.value)}
                className="w-full text-xs font-medium bg-white border border-gray-300 rounded-md py-1.5 pl-2 pr-7 text-gray-700 appearance-none focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer truncate shadow-sm"
              >
                {statements.map((s) => (
                  <option key={s.id} value={s.id}>
                    #{s.id}: {s.original_filename || "Statement"} {s.tier ? `(${s.tier.replace('_', ' ')})` : `(${s.status})`}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-gray-400 absolute right-2 top-2 pointer-events-none" />
            </div>
          ) : (
            <div className="text-xs text-gray-400 py-1">No statements uploaded yet</div>
          )}

          {currentStatement && (
            <div className="mt-2 text-[11px] text-gray-500 flex items-center justify-between gap-1">
              <span className="truncate flex-1" title={currentStatement.original_filename || ""}>
                {currentStatement.original_filename}
              </span>
              <span
                className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                  currentStatement.tier === "CONFIRMED_SUSPICIOUS"
                    ? "bg-red-100 text-red-700"
                    : currentStatement.tier === "LIKELY_LEGITIMATE"
                    ? "bg-green-100 text-green-700"
                    : currentStatement.tier === "REVIEW_REQUIRED"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {currentStatement.tier ? currentStatement.tier.replace("_", " ") : currentStatement.status}
              </span>
            </div>
          )}
        </div>

        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {navItems.map(({ to, label, icon: Icon, exact, activePath }) => {
            const isItemActive = exact
              ? location.pathname === "/"
              : activePath
              ? location.pathname.startsWith(activePath)
              : false;

            return (
              <NavLink
                key={label}
                to={to}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isItemActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="p-3 border-t border-gray-200 space-y-2">
          {statements.length > 0 && (
            <button
              onClick={handlePurgeAll}
              className="w-full text-xs text-gray-500 hover:text-red-600 hover:bg-red-50 p-1.5 rounded flex items-center justify-center gap-1.5 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" /> Purge All Data
            </button>
          )}
          <div className="text-[11px] text-gray-400 text-center">
            Fully offline &mdash; no data leaves this machine
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-x-hidden overflow-y-auto min-w-0">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/review" element={<ExtractionReviewPage />} />
          <Route path="/review/:id" element={<ExtractionReviewPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/dashboard/:id" element={<DashboardPage />} />
          <Route path="/evidence" element={<EvidenceExplorerPage />} />
          <Route path="/evidence/:id" element={<EvidenceExplorerPage />} />
          <Route path="/graph" element={<ProofGraphPage />} />
          <Route path="/graph/:id" element={<ProofGraphPage />} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  return (
    <StatementProvider>
      <AppLayout />
    </StatementProvider>
  );
}

export default App;
