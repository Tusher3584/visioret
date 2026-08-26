/** Shared formatting helpers, so numbers and dates read identically everywhere. */

export function percent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function fixed(value: number, decimals = 3): string {
  return value.toFixed(decimals);
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatCount(value: number): string {
  return value.toLocaleString();
}
