import { useState, useEffect } from "react";
import { Routes, Route, NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  Upload,
  FileSearch,
  LayoutDashboard,
  Search,
  GitGraph,
  ShieldCheck,
  Trash2,
  ChevronDown,
  Menu,
  X,
  WifiOff,
  Lock,
  Landmark,
} from "lucide-react";
import { UploadPage } from "./pages/UploadPage";
import { ExtractionReviewPage } from "./pages/ExtractionReviewPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EvidenceExplorerPage } from "./pages/EvidenceExplorerPage";
import { ProofGraphPage } from "./pages/ProofGraphPage";
import { BankIntelligencePage } from "./pages/BankIntelligencePage";
import { BankProfilePage } from "./pages/BankProfilePage";
import { StatementProvider, useStatement } from "./lib/StatementContext";
import { TIER_META } from "./components/ui";

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { statements, currentId, currentStatement, setCurrentId, purgeAll } = useStatement();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Close mobile sidebar on page navigation, and start each screen at the top
  // rather than inheriting the previous page's scroll offset.
  useEffect(() => {
    setMobileMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [location.pathname]);

  // Close mobile sidebar on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileMenuOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const analysed = currentStatement?.tier != null;

  // The console is a linear workflow: ingest, verify, then investigate.
  const navItems = [
    {
      step: 1,
      to: "/",
      label: "Upload & Cases",
      hint: "Ingest statements",
      icon: Upload,
      exact: true,
      locked: false,
    },
    {
      step: 2,
      to: currentId ? `/review/${currentId}` : "/review",
      label: "Extraction Review",
      hint: "Verify column mapping",
      icon: FileSearch,
      activePath: "/review",
      locked: !currentId,
    },
    {
      step: 3,
      to: currentId ? `/dashboard/${currentId}` : "/dashboard",
      label: "Risk Dashboard",
      hint: "Why it was flagged",
      icon: LayoutDashboard,
      activePath: "/dashboard",
      locked: !currentId,
    },
    {
      step: 4,
      to: currentId ? `/evidence/${currentId}` : "/evidence",
      label: "Evidence Explorer",
      hint: "Timeline & audit trail",
      icon: Search,
      activePath: "/evidence",
      locked: !currentId,
    },
    {
      step: 5,
      to: currentId ? `/graph/${currentId}` : "/graph",
      label: "Proof Graph",
      hint: "Fund-flow network",
      icon: GitGraph,
      activePath: "/graph",
      locked: !currentId,
    },
  ];

  const intelItems = [
    {
      to: "/banks",
      label: "Bank Intelligence",
      hint: "Institution profiles",
      icon: Landmark,
      activePath: "/banks",
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
    if (window.confirm("Purge every statement, transaction and analysis record from this machine?")) {
      await purgeAll();
      setMobileMenuOpen(false);
      navigate("/");
    }
  };

  const tierMeta = currentStatement?.tier ? TIER_META[currentStatement.tier] : undefined;

  return (
    <div className="flex min-h-screen flex-col bg-ink-50 text-ink-900 lg:flex-row">
      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-800 bg-ink-950 px-4 py-2.5 lg:hidden">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600">
            <ShieldCheck className="h-4 w-4 text-white" />
          </span>
          <span className="text-sm font-semibold text-white">MuleGuard</span>
        </div>

        <div className="flex items-center gap-2">
          {currentStatement && (
            <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-semibold text-ink-100">
              Case #{currentStatement.id}
            </span>
          )}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="rounded-lg p-1.5 text-ink-200 hover:bg-white/10 hover:text-white"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </header>

      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-ink-950/60 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[264px] shrink-0 transform flex-col bg-ink-950 transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 ${
          mobileMenuOpen ? "translate-x-0 shadow-panel" : "-translate-x-full"
        }`}
      >
        {/* Brand */}
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 shadow-inset">
              <ShieldCheck className="h-5 w-5 text-white" />
            </span>
            <div>
              <p className="text-[15px] font-semibold leading-tight text-white">MuleGuard</p>
              <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-400">
                AML Analyst Console
              </p>
            </div>
          </div>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="rounded-md p-1 text-ink-400 hover:bg-white/10 hover:text-white lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Active case */}
        <div className="border-b border-white/10 px-3 py-3">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-400">
              Active case
            </span>
            {statements.length > 0 && (
              <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-semibold text-ink-100">
                {statements.length} loaded
              </span>
            )}
          </div>

          {statements.length > 0 ? (
            <>
              <div className="relative">
                <select
                  value={currentId || ""}
                  onChange={(e) => handleSelectStatement(e.target.value)}
                  className="w-full cursor-pointer truncate rounded-lg border border-white/10 bg-white/5 py-2 pl-2.5 pr-8 text-xs font-medium text-white outline-none transition-colors hover:border-white/20 focus:border-brand-500"
                >
                  {statements.map((s) => (
                    <option key={s.id} value={s.id} className="bg-white text-ink-900">
                      #{s.id} · {s.original_filename || "Statement"}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-3.5 w-3.5 text-ink-400" />
              </div>

              {currentStatement && (
                <div className="mt-2 rounded-lg border border-white/10 bg-white/5 px-2.5 py-2">
                  <p
                    className="truncate text-[11px] font-medium text-ink-100"
                    title={currentStatement.original_filename || ""}
                  >
                    {currentStatement.original_filename || "Untitled statement"}
                  </p>
                  <div className="mt-1.5 flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-ink-300">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${tierMeta ? tierMeta.dot : "bg-ink-400"}`}
                      />
                      {tierMeta ? tierMeta.label : currentStatement.status}
                    </span>
                    {currentStatement.fused_score != null && (
                      <span className="num text-[11px] font-bold text-white">
                        {currentStatement.fused_score.toFixed(0)}
                        <span className="text-ink-400">/100</span>
                      </span>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="rounded-lg border border-dashed border-white/15 px-2.5 py-3 text-center text-[11px] text-ink-400">
              No statements uploaded yet
            </p>
          )}
        </div>

        {/* Workflow navigation */}
        <nav className="scroll-slim flex-1 overflow-y-auto px-2 py-3">
          <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-500">
            Investigation workflow
          </p>
          <div className="space-y-0.5">
            {navItems.map(({ step, to, label, hint, icon: Icon, exact, activePath, locked }) => {
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
                  className={`group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 transition-colors ${
                    isItemActive
                      ? "bg-white/10 text-white"
                      : locked
                      ? "text-ink-500 hover:bg-white/5"
                      : "text-ink-200 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  {isItemActive && (
                    <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-r-full bg-brand-500" />
                  )}
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border text-[10px] font-bold ${
                      isItemActive
                        ? "border-brand-500/40 bg-brand-600/20 text-brand-300"
                        : "border-white/10 bg-white/5 text-ink-400 group-hover:text-ink-200"
                    }`}
                  >
                    {step}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5">
                      <Icon className="h-3.5 w-3.5 shrink-0 opacity-80" />
                      <span className="truncate text-[13px] font-medium">{label}</span>
                      {locked && <Lock className="h-3 w-3 shrink-0 text-ink-500" />}
                    </span>
                    <span className="block truncate text-[10px] text-ink-500">{hint}</span>
                  </span>
                </NavLink>
              );
            })}
          </div>

          {currentId && !analysed && (
            <p className="mx-2 mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-2.5 py-2 text-[10px] leading-relaxed text-amber-200">
              Case #{currentId} has not been analysed yet — confirm the extraction in step 2 to unlock
              scoring.
            </p>
          )}

          <p className="px-2 pb-1.5 pt-4 text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-500">
            Network intelligence
          </p>
          <div className="space-y-0.5">
            {intelItems.map(({ to, label, hint, icon: Icon, activePath }) => {
              const isItemActive = location.pathname.startsWith(activePath);
              return (
                <NavLink
                  key={label}
                  to={to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 transition-colors ${
                    isItemActive ? "bg-white/10 text-white" : "text-ink-200 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  {isItemActive && (
                    <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-r-full bg-brand-500" />
                  )}
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border ${
                      isItemActive
                        ? "border-brand-500/40 bg-brand-600/20 text-brand-300"
                        : "border-white/10 bg-white/5 text-ink-400 group-hover:text-ink-200"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium">{label}</span>
                    <span className="block truncate text-[10px] text-ink-500">{hint}</span>
                  </span>
                </NavLink>
              );
            })}
          </div>
        </nav>

        {/* Footer */}
        <div className="border-t border-white/10 px-3 py-3">
          {statements.length > 0 && (
            <button
              onClick={handlePurgeAll}
              className="mb-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-white/10 py-1.5 text-[11px] font-medium text-ink-300 transition-colors hover:border-red-500/40 hover:bg-red-500/10 hover:text-red-300"
            >
              <Trash2 className="h-3.5 w-3.5" /> Purge all local data
            </button>
          )}
          <div className="flex items-center justify-center gap-1.5 text-[10px] text-ink-500">
            <WifiOff className="h-3 w-3" />
            <span>Air-gapped · v0.1.0 · no data leaves this machine</span>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
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
          <Route path="/banks" element={<BankIntelligencePage />} />
          <Route path="/banks/:code" element={<BankProfilePage />} />
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
