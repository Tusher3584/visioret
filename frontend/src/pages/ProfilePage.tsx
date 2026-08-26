import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, updateProfile } from "../api/client";
import { Avatar } from "../components/layout/Avatar";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { useAuth } from "../context/AuthContext";

export function ProfilePage() {
  const { user, isLoading, setUser } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    if (user) setName(user.name);
  }, [user]);

  // Nothing to edit when signed out.
  useEffect(() => {
    if (!isLoading && !user) navigate("/login", { replace: true });
  }, [isLoading, user, navigate]);

  if (!user) return null;

  const nameChanged = name.trim() !== user.name;
  const changingPassword = newPassword.length > 0;
  const canSave = (nameChanged || changingPassword) && !isSaving;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setSaved(null);
    try {
      const updated = await updateProfile({
        ...(nameChanged ? { name: name.trim() } : {}),
        ...(changingPassword
          ? { current_password: currentPassword, new_password: newPassword }
          : {}),
      });
      setUser(updated);
      setCurrentPassword("");
      setNewPassword("");
      setSaved(changingPassword ? "Profile and password updated." : "Profile updated.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your changes.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Your profile"
        description="Update how you appear on the scans and reviews you record."
      />

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,460px)_280px]">
        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4 border border-line bg-surface p-5 rounded-[3px]"
        >
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink">Display name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={120}
              className={INPUT}
            />
            <span className="text-[11px] text-subtle">
              Shown as the author of scans you submit and reviews you record.
            </span>
          </label>

          <fieldset className="flex flex-col gap-3 border-t border-line pt-4">
            <legend className="sr-only">Change password</legend>
            <p className="text-xs font-medium text-ink">Change password</p>
            <label className="flex flex-col gap-1.5">
              <span className="text-[11px] text-muted">Current password</span>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                className={INPUT}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-[11px] text-muted">New password</span>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                minLength={8}
                autoComplete="new-password"
                className={INPUT}
              />
              <span className="text-[11px] text-subtle">
                Leave blank to keep your current password. At least 8 characters.
              </span>
            </label>
          </fieldset>

          {error && (
            <p role="alert" className="text-xs text-rose-700 dark:text-rose-300">
              {error}
            </p>
          )}
          {saved && (
            <p role="status" className="text-xs text-emerald-700 dark:text-emerald-400">
              {saved}
            </p>
          )}

          <div className="flex items-center gap-2 border-t border-line pt-4">
            <Button type="submit" variant="primary" size="sm" disabled={!canSave}>
              {isSaving ? "Saving…" : "Save changes"}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => navigate(-1)}>
              Cancel
            </Button>
          </div>
        </form>

        <aside className="divide-y divide-line border border-line bg-surface rounded-[3px]">
          <div className="flex items-center gap-3 px-4 py-4">
            <Avatar seed={user.email} size={44} />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">{user.name}</p>
              <p className="truncate text-xs text-muted">{user.email}</p>
            </div>
          </div>
          <dl className="flex flex-col gap-2 px-4 py-3 text-xs">
            <Row label="Role" value={user.role} mono />
            <Row label="Account ID" value={`#${user.id}`} mono />
          </dl>
          <p className="px-4 py-3 text-[11px] leading-snug text-subtle">
            Your picture is generated from your email address and cannot be changed. Email and role
            are fixed here — role is granted by an administrator.
          </p>
        </aside>
      </div>
    </div>
  );
}

const INPUT =
  "rounded-[3px] border border-line-strong bg-surface px-2.5 py-2 text-sm text-ink placeholder:text-subtle";

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-subtle">{label}</dt>
      <dd className={`text-ink ${mono ? "font-mono text-[11px] uppercase" : ""}`}>{value}</dd>
    </div>
  );
}
