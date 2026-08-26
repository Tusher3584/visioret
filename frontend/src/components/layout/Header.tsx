import { motion, useReducedMotion } from "framer-motion";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { LogoMark } from "./LogoMark";
import { SystemStatus } from "./SystemStatus";
import { ThemeToggle } from "./ThemeToggle";

const NAV_LINKS = [
  { to: "/", label: "Predict", end: true, reviewerOnly: false },
  { to: "/history", label: "History", end: false, reviewerOnly: false },
  // Metrics is reviewer-only server-side; hiding it here avoids offering a
  // link that would only return 403.
  { to: "/metrics", label: "Metrics", end: false, reviewerOnly: true },
];

/**
 * The header wraps rather than scrolls on narrow screens: brand and controls
 * hold the first row, and the nav drops to a full-width tab strip beneath.
 * Everything stays reachable down to 320px without a hamburger, since there
 * are only three destinations.
 */
export function Header() {
  const { user, isReviewer, isLoading, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-3 px-4 sm:gap-x-4 sm:px-6">
        <NavLink to="/" className="flex items-center gap-2.5 py-2.5" aria-label="Visioret home">
          <LogoMark />
          <span className="flex flex-col leading-none">
            <span className="text-[15px] font-semibold tracking-[0.14em] text-ink">VISIORET</span>
            <span className="mt-1 hidden text-[10px] tracking-[0.02em] text-subtle lg:block">
              Explainable AI · Retinal OCT
            </span>
          </span>
        </NavLink>

        <div className="ml-auto flex items-center gap-2 py-2.5 sm:gap-3">
          <SystemStatus />
          <ThemeToggle />
          {!isLoading &&
            (user ? (
              <div className="flex items-center gap-2 text-xs">
                <span className="hidden text-muted md:inline">
                  {user.name}
                  <span className="ml-1.5 font-mono text-[10px] uppercase tracking-wider text-subtle">
                    {user.role}
                  </span>
                </span>
                <button
                  onClick={() => {
                    logout();
                    navigate("/");
                  }}
                  className="whitespace-nowrap font-medium text-accent hover:underline"
                >
                  Sign out
                </button>
              </div>
            ) : (
              <NavLink
                to="/login"
                className="whitespace-nowrap text-xs font-medium text-accent hover:underline"
              >
                Sign in
              </NavLink>
            ))}
        </div>

        <nav
          aria-label="Primary"
          className="order-last flex w-full items-stretch border-t border-line sm:order-none sm:ml-4 sm:w-auto sm:border-t-0"
        >
          {NAV_LINKS.filter((link) => !link.reviewerOnly || isReviewer).map((link) => (
            <NavItem key={link.to} to={link.to} end={link.end} label={link.label} />
          ))}
        </nav>
      </div>
    </header>
  );
}

/**
 * Active state is a bottom rule that slides between items -- a tab-strip
 * convention from technical software, rather than a floating pill. On desktop
 * the item is header-height so the rule lands on the header's own bottom edge.
 */
function NavItem({ to, end, label }: { to: string; end: boolean; label: string }) {
  const reduceMotion = useReducedMotion();
  return (
    <NavLink
      to={to}
      end={end}
      className="relative flex h-11 flex-1 items-center justify-center text-[13px] font-medium transition-colors sm:h-14 sm:flex-none sm:justify-start sm:px-4"
    >
      {({ isActive }) => (
        <>
          <span className={isActive ? "text-ink" : "text-muted hover:text-ink"}>{label}</span>
          {isActive && (
            <motion.span
              layoutId="nav-underline"
              className="absolute inset-x-4 bottom-0 h-0.5 bg-accent sm:inset-x-3 sm:-bottom-px"
              transition={
                reduceMotion
                  ? { duration: 0 }
                  : { type: "spring", stiffness: 520, damping: 38 }
              }
            />
          )}
        </>
      )}
    </NavLink>
  );
}
