import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import { getToken, setToken } from "../auth/token";
import { LoginPage } from "./LoginPage";

vi.mock("../api/auth", () => ({ requestLogin: vi.fn(), fetchMe: vi.fn() }));
vi.mock("../components/HealthBadge", () => ({ HealthBadge: () => <span>health</span> }));

import { fetchMe, requestLogin } from "../api/auth";
const loginMock = vi.mocked(requestLogin);
const meMock = vi.mocked(fetchMe);

const TOKEN = { access_token: "tok-123", token_type: "bearer", expires_in: 3600, role: "admin" };
const ADMIN = { username: "admin", role: "admin" };

function renderLogin(entry: string | { pathname: string; state?: unknown } = "/login") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<p>Feed page</p>} />
          <Route path="/alerts/:id" element={<p>Alert detail page</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function fill(username: string, password: string) {
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: username } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
}

const submit = () => fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

beforeEach(() => {
  sessionStorage.clear();
  loginMock.mockReset();
  meMock.mockReset();
});

describe("LoginPage", () => {
  it("shows an error and clears the password on a wrong password", async () => {
    loginMock.mockRejectedValue(new ApiError(401, "Incorrect username or password"));
    renderLogin();
    fill("admin", "wrong");
    submit();
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect username or password.");
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(screen.getByLabelText("Username")).toHaveValue("admin");
    expect(getToken()).toBeNull();
    expect(screen.queryByText("Feed page")).not.toBeInTheDocument();
  });

  it("asks for both fields without calling the API", () => {
    renderLogin();
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter your username and password.");
    fill("admin", "");
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter your username and password.");
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("explains when the server cannot be reached", async () => {
    loginMock.mockRejectedValue(new ApiError(0, "Cannot reach the server"));
    renderLogin();
    fill("admin", "secret");
    submit();
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server. Check that the API is running");
  });

  it("signs in, stores the token and lands on the feed", async () => {
    loginMock.mockResolvedValue(TOKEN);
    meMock.mockResolvedValue(ADMIN);
    renderLogin();
    fill("  admin ", "secret");
    submit();
    expect(await screen.findByText("Feed page")).toBeInTheDocument();
    expect(loginMock).toHaveBeenCalledWith("admin", "secret");
    expect(getToken()).toBe("tok-123");
  });

  it("disables the form while signing in", async () => {
    let finish: (value: typeof TOKEN) => void = () => {};
    loginMock.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    meMock.mockResolvedValue(ADMIN);
    renderLogin();
    fill("admin", "secret");
    submit();
    expect(await screen.findByRole("button", { name: "Signing in..." })).toBeDisabled();
    expect(screen.getByLabelText("Username")).toBeDisabled();
    await act(async () => finish(TOKEN));
    expect(await screen.findByText("Feed page")).toBeInTheDocument();
  });

  it("forgets the token and shows the error when the profile lookup fails", async () => {
    loginMock.mockResolvedValue(TOKEN);
    meMock.mockRejectedValue(new ApiError(500, "boom"));
    renderLogin();
    fill("admin", "secret");
    submit();
    expect(await screen.findByRole("alert")).toHaveTextContent("The server had a problem (HTTP 500)");
    expect(getToken()).toBeNull();
  });

  it("returns to the page the user was trying to open", async () => {
    loginMock.mockResolvedValue(TOKEN);
    meMock.mockResolvedValue(ADMIN);
    renderLogin({ pathname: "/login", state: { from: "/alerts/5" } });
    fill("admin", "secret");
    submit();
    expect(await screen.findByText("Alert detail page")).toBeInTheDocument();
  });

  it("skips the form when a valid session already exists", async () => {
    setToken("existing");
    meMock.mockResolvedValue(ADMIN);
    renderLogin();
    await waitFor(() => expect(screen.getByText("Feed page")).toBeInTheDocument());
  });
});
