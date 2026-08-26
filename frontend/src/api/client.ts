import type {
  AdminUser,
  EvaluationMetric,
  Feedback,
  FeedbackCreate,
  HealthResponse,
  LoginRequest,
  PredictionResponse,
  ProfileUpdate,
  RegisterRequest,
  ScanDetail,
  ScanSummary,
  TokenResponse,
  User,
} from "./types";

import { getAnonSessionId } from "../lib/anonSession";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";
const TOKEN_STORAGE_KEY = "visioret_token";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Identity headers for the scan endpoints. When signed in that's the bearer
 * token; when not, it's the anonymous session id that scopes history to this
 * browser session. Sending both is harmless -- the server ignores the session
 * id for authenticated callers.
 */
function scanHeaders(): Record<string, string> {
  const headers: Record<string, string> = { ...authHeaders() };
  const session = getAnonSessionId();
  if (session) headers["X-Anon-Session"] = session;
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON -- fall back to statusText
    }
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export function mediaUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  return handleResponse<HealthResponse>(response);
}

export async function register(body: RegisterRequest): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<TokenResponse>(response);
}

export async function login(body: LoginRequest): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<TokenResponse>(response);
}

export async function fetchMe(): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, { headers: authHeaders() });
  return handleResponse<User>(response);
}

export async function fetchAdminUsers(): Promise<AdminUser[]> {
  const response = await fetch(`${API_BASE_URL}/api/admin/users`, { headers: authHeaders() });
  return handleResponse<AdminUser[]>(response);
}

export async function setUserRole(userId: number, role: string): Promise<AdminUser> {
  const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/role`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ role }),
  });
  return handleResponse<AdminUser>(response);
}

export async function updateProfile(body: ProfileUpdate): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  return handleResponse<User>(response);
}

export async function predict(file: File): Promise<PredictionResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/predict`, {
    method: "POST",
    headers: scanHeaders(),
    body: formData,
  });
  return handleResponse<PredictionResponse>(response);
}

// These three send the token because what they return now depends on who is
// asking: scan visibility is scoped by owner/role, and metrics are
// reviewer-only. Without the header the API would treat the caller as
// anonymous and silently return the wrong set.
export async function listScans(): Promise<ScanSummary[]> {
  const response = await fetch(`${API_BASE_URL}/api/scans`, { headers: scanHeaders() });
  return handleResponse<ScanSummary[]>(response);
}

export async function getScan(scanId: number): Promise<ScanDetail> {
  const response = await fetch(`${API_BASE_URL}/api/scans/${scanId}`, { headers: scanHeaders() });
  return handleResponse<ScanDetail>(response);
}

export async function fetchMetrics(): Promise<EvaluationMetric[]> {
  const response = await fetch(`${API_BASE_URL}/api/metrics`, { headers: authHeaders() });
  return handleResponse<EvaluationMetric[]>(response);
}

export async function submitFeedback(scanId: number, body: FeedbackCreate): Promise<Feedback> {
  const response = await fetch(`${API_BASE_URL}/api/scans/${scanId}/feedback`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  return handleResponse<Feedback>(response);
}
