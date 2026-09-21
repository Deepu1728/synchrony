import { ApiError } from "../api/client";

export function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Incorrect username or password.";
    if (error.status === 0) return "Cannot reach the server. Check that the API is running and try again.";
    if (error.status === 429) return "Too many attempts. Wait a moment and try again.";
    if (error.status >= 500) return `The server had a problem (HTTP ${error.status}). Try again in a moment.`;
    return error.message;
  }
  return "Something went wrong. Try again.";
}
