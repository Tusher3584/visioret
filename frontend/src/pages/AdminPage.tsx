import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, fetchAdminUsers, setUserRole } from "../api/client";
import type { AdminUser } from "../api/types";
import { Avatar } from "../components/layout/Avatar";
import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "../components/states/States";
import { useAuth } from "../context/AuthContext";
import { formatDate, formatCount } from "../lib/format";

export function AdminPage() {
  const { isAdmin, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchAdminUsers()
      .then(setUsers)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load the account list."),
      );
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!isAdmin) {
      navigate("/", { replace: true });
      return;
    }
    load();
  }, [authLoading, isAdmin, navigate, load]);

  async function changeRole(user: AdminUser, role: string) {
    setBusyId(user.id);
    setError(null);
    setNotice(null);
    try {
      const updated = await setUserRole(user.id, role);
      setUsers((current) =>
        current ? current.map((u) => (u.id === updated.id ? updated : u)) : current,
      );
      setNotice(`${updated.name} is now a ${updated.role}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change that role.");
    } finally {
      setBusyId(null);
    }
  }

  if (!isAdmin) return null;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Accounts"
        description="Every registered account. Promote a viewer to reviewer to let them record corrections and read model metrics."
      />

      {error && <ErrorState message={error} />}
      {notice && (
        <p
          role="status"
          className="rounded-[3px] border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
        >
          {notice}
        </p>
      )}

      {!error && !users && <LoadingState label="Loading accounts" />}

      {!error && users && users.length === 0 && (
        <EmptyState title="No accounts" description="Nobody has registered yet." />
      )}

      {!error && users && users.length > 0 && (
        <div className="overflow-hidden border border-line bg-surface rounded-[3px]">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">Registered accounts and their roles</caption>
            <thead>
              <tr className="border-b border-line text-left">
                <Th>Account</Th>
                <Th className="hidden md:table-cell">Registered</Th>
                <Th className="hidden lg:table-cell">Scans</Th>
                <Th className="hidden lg:table-cell">Reviews</Th>
                <Th>Role</Th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b border-line/70 last:border-0">
                  <td className="px-3 py-2.5">
                    <span className="flex items-center gap-2.5">
                      <Avatar seed={user.email} size={26} />
                      <span className="min-w-0">
                        <span className="flex items-center gap-1.5">
                          <span className="truncate text-xs font-medium text-ink">{user.name}</span>
                          {user.is_self && (
                            <span className="rounded-[2px] bg-raised px-1 py-0.5 text-[9px] uppercase tracking-wider text-subtle">
                              you
                            </span>
                          )}
                        </span>
                        <span className="block truncate text-[11px] text-muted">{user.email}</span>
                      </span>
                    </span>
                  </td>

                  <td className="hidden px-3 py-2.5 md:table-cell">
                    <span className="font-mono text-[11px] text-muted">
                      {formatDate(user.created_at)}
                    </span>
                  </td>

                  <td className="hidden px-3 py-2.5 lg:table-cell">
                    <span className="font-mono text-xs tabular-nums text-muted">
                      {formatCount(user.scans_submitted)}
                    </span>
                  </td>

                  <td className="hidden px-3 py-2.5 lg:table-cell">
                    <span className="font-mono text-xs tabular-nums text-muted">
                      {formatCount(user.reviews_recorded)}
                    </span>
                  </td>

                  <td className="px-3 py-2.5">
                    {user.is_editable && !user.is_self ? (
                      <label className="flex items-center gap-2">
                        <span className="sr-only">Role for {user.name}</span>
                        <select
                          value={user.role}
                          disabled={busyId === user.id}
                          onChange={(e) => changeRole(user, e.target.value)}
                          className="rounded-[3px] border border-line-strong bg-surface px-2 py-1 text-xs text-ink disabled:opacity-50"
                        >
                          <option value="viewer">viewer</option>
                          <option value="reviewer">reviewer</option>
                        </select>
                      </label>
                    ) : (
                      <span className="inline-flex items-center gap-1.5">
                        <span className="font-mono text-[11px] uppercase tracking-wider text-ink">
                          {user.role}
                        </span>
                        <span className="text-[10px] text-subtle">
                          {user.is_self ? "(cannot edit own role)" : "(managed in database)"}
                        </span>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[11px] leading-relaxed text-subtle">
        The <span className="font-mono">admin</span> role cannot be granted here — it is set
        directly against the database (<span className="font-mono">backend/grant_role.py</span>), so
        administrative privilege always originates from someone with database access rather than
        from the application. Admins can neither edit their own role nor another admin's.
      </p>
    </div>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      scope="col"
      className={`px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.09em] text-subtle ${className}`}
    >
      {children}
    </th>
  );
}
