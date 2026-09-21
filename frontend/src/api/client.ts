import { clearToken, getToken } from "../auth/token";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  form?: Record<string, string>;
  signal?: AbortSignal;
};

let unauthorizedHandler: (() => void) | null = null;

export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

async function readDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => (typeof d?.msg === "string" ? d.msg : "Invalid input")).join("; ");
    }
  } catch {
    /* body was not JSON */
  }
  return `Request failed (HTTP ${res.status})`;
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (options.form) {
    body = new URLSearchParams(options.form);
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { method: options.method ?? "GET", headers, body, signal: options.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Cannot reach the server");
  }

  if (!res.ok) {
    if (res.status === 401 && token) {
      clearToken();
      unauthorizedHandler?.();
    }
    throw new ApiError(res.status, await readDetail(res));
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}
