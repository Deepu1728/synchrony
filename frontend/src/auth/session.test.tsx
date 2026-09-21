import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { Layout } from "../components/Layout";
import { AuthProvider } from "./AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";
import { getToken, setToken } from "./token";

vi.mock("../api/auth", () => ({ requestLogin: vi.fn(), fetchMe: vi.fn() }));
vi.mock("../components/HealthBadge", () => ({ HealthBadge: () => <span>health</span> }));
vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, onUnauthorized: vi.fn() };
});

import { fetchMe } from "../api/auth";
import { onUnauthorized } from "../api/client";
const meMock = vi.mocked(fetchMe);
const handlerMock = vi.mocked(onUnauthorized);

const ADMIN = { username: "admin", role: "admin" };

function renderApp(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>Login page</p>} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<p>Feed page</p>} />
              <Route path="/metrics" element={<p>Metrics page</p>} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  meMock.mockReset();
  handlerMock.mockReset();
});

describe("protected routes and session", () => {
  it("sends visitors without a session to the login page", () => {
    renderApp("/metrics");
    expect(screen.getByText("Login page")).toBeInTheDocument();
    expect(screen.queryByText("Metrics page")).not.toBeInTheDocument();
    expect(meMock).not.toHaveBeenCalled();
  });

  it("keeps you signed in after a reload (stored token is verified)", async () => {
    setToken("stored");
    meMock.mockResolvedValue(ADMIN);
    renderApp();
    expect(screen.getByText("Checking your session...")).toBeInTheDocument();
    expect(await screen.findByText("Feed page")).toBeInTheDocument();
    expect(screen.getByText("admin", { selector: ".user-name" })).toBeInTheDocument();
    expect(screen.getByText("admin", { selector: ".user-role" })).toBeInTheDocument();
  });

  it("drops a rejected token and asks you to sign in again", async () => {
    setToken("expired");
    meMock.mockRejectedValue(new ApiError(401, "Could not validate credentials"));
    renderApp();
    expect(await screen.findByText("Login page")).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });

  it.each([
    [0, "Cannot reach the server"],
    [500, "Internal Server Error"],
    [502, "Bad Gateway"],
    [503, "Service Unavailable"],
    [504, "Gateway Timeout"],
  ])("keeps the token and offers a retry when the server fails (HTTP %i)", async (status, detail) => {
    setToken("stored");
    meMock.mockRejectedValueOnce(new ApiError(status, detail));
    renderApp();
    expect(await screen.findByText("Cannot reach the server.")).toBeInTheDocument();
    expect(getToken()).toBe("stored");

    meMock.mockResolvedValue(ADMIN);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Feed page")).toBeInTheDocument();
  });

  it("also drops the token on a 403", async () => {
    setToken("stored");
    meMock.mockRejectedValue(new ApiError(403, "Forbidden"));
    renderApp();
    expect(await screen.findByText("Login page")).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });

  it("logs out: clears the token and returns to the login page", async () => {
    setToken("stored");
    meMock.mockResolvedValue(ADMIN);
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: "Log out" }));
    expect(await screen.findByText("Login page")).toBeInTheDocument();
    expect(getToken()).toBeNull();
  });

  it("returns to the login page when a request later reports an expired session", async () => {
    setToken("stored");
    meMock.mockResolvedValue(ADMIN);
    renderApp();
    await screen.findByText("Feed page");
    const handler = handlerMock.mock.calls.map((call) => call[0]).filter(Boolean).at(-1)!;
    act(() => handler());
    await waitFor(() => expect(screen.getByText("Login page")).toBeInTheDocument());
  });
});
