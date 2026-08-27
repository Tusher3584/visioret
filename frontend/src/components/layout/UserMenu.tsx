import { motion, useReducedMotion } from "framer-motion";
import { canAnimate } from "../../lib/motion";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { User } from "../../api/types";
import { Avatar } from "./Avatar";

interface Props {
  user: User;
  onSignOut: () => void;
}

/**
 * Avatar button with a dropdown menu.
 *
 * Implements the menu-button pattern properly: aria-haspopup/aria-expanded on
 * the trigger, role="menu"/"menuitem" on the list, Escape and click-outside to
 * dismiss, arrow keys to move between items, and focus returned to the trigger
 * on close. The menu is closed on route change too, so navigating away never
 * leaves it hanging open.
 */
export function UserMenu({ user, onSignOut }: Props) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const items = Array.from(
          menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
        );
        if (items.length === 0) return;
        const index = items.indexOf(document.activeElement as HTMLElement);
        const next =
          event.key === "ArrowDown"
            ? (index + 1) % items.length
            : (index - 1 + items.length) % items.length;
        items[next].focus();
      }
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  // Move focus into the menu when it opens via keyboard.
  useEffect(() => {
    if (!open) return;
    const first = menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]');
    first?.focus();
  }, [open]);

  function go(path: string) {
    setOpen(false);
    navigate(path);
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${user.name}`}
        className="grid place-items-center rounded-full ring-1 ring-line transition-shadow hover:ring-line-strong"
      >
        <Avatar seed={user.email} size={28} />
      </button>

      {/* Entrance only, and no AnimatePresence: an exit animation would keep the
          menu mounted until it finished, and a menu that is invisible but still
          holds focusable "Sign out" items is a keyboard trap. Closing unmounts
          immediately and unconditionally. */}
      {open && (
          <motion.div
            ref={menuRef}
            role="menu"
            aria-label="Account"
            initial={canAnimate(reduceMotion) ? { opacity: 0, y: -4, scale: 0.97 } : false}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.14, ease: "easeOut" }}
            className="absolute right-0 top-[calc(100%+8px)] z-50 w-60 origin-top-right overflow-hidden rounded-[3px] border border-line bg-surface shadow-lg"
          >
            <div className="flex items-center gap-2.5 border-b border-line px-3 py-2.5">
              <Avatar seed={user.email} size={32} />
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-ink">{user.name}</p>
                <p className="truncate text-[11px] text-muted">{user.email}</p>
                <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-subtle">
                  {user.role}
                </p>
              </div>
            </div>

            <div className="p-1">
              <MenuItem onSelect={() => go("/profile")}>
                <PencilIcon />
                Edit profile
              </MenuItem>
              <MenuItem
                onSelect={() => {
                  setOpen(false);
                  onSignOut();
                }}
              >
                <SignOutIcon />
                Sign out
              </MenuItem>
            </div>
          </motion.div>
      )}
    </div>
  );
}

function MenuItem({
  onSelect,
  children,
}: {
  onSelect: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      role="menuitem"
      onClick={onSelect}
      className="flex w-full items-center gap-2.5 rounded-[2px] px-2.5 py-2 text-left text-xs font-medium text-ink transition-colors hover:bg-raised focus:bg-raised focus:outline-none"
    >
      {children}
    </button>
  );
}

function PencilIcon() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="shrink-0 text-muted"
    >
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
    </svg>
  );
}

function SignOutIcon() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="shrink-0 text-muted"
    >
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5M21 12H9" />
    </svg>
  );
}
