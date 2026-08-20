import type { HealthResponse, PredictionResponse, ScanDetail, ScanSummary } from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
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

export async function predict(file: File): Promise<PredictionResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/predict`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<PredictionResponse>(response);
}

export async function listScans(): Promise<ScanSummary[]> {
  const response = await fetch(`${API_BASE_URL}/api/scans`);
  return handleResponse<ScanSummary[]>(response);
}

export async function getScan(scanId: number): Promise<ScanDetail> {
  const response = await fetch(`${API_BASE_URL}/api/scans/${scanId}`);
  return handleResponse<ScanDetail>(response);
}
