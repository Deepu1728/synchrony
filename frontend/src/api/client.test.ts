import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearToken, getToken, setToken } from "../auth/token";
import { api, ApiError, onUnauthorized } from "./client";

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;
const reply = (data: unknown, status = 200) => fetchMock.mockImplementation(() => Promise.resolve(json(data, status)));

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  clearToken();
  onUnauthorized(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("calls the API under /api and returns parsed JSON", async () => {
    reply({ status: "ok" });
    await expect(api("/health")).resolves.toEqual({ status: "ok" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/health");
  });

  it("attaches the bearer token only when signed in", async () => {
    reply({});
    await api("/metrics");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
    setToken("abc123");
    await api("/metrics");
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe("Bearer abc123");
  });

  it("sends JSON bodies and url-encoded forms", async () => {
    reply({});
    await api("/feedback", { method: "POST", body: { verdict: "fraud" } });
    const [, jsonInit] = fetchMock.mock.calls[0];
    expect(jsonInit.method).toBe("POST");
    expect(jsonInit.headers["Content-Type"]).toBe("application/json");
    expect(jsonInit.body).toBe('{"verdict":"fraud"}');

    await api("/auth/login", { method: "POST", form: { username: "admin", password: "x y" } });
    const [, formInit] = fetchMock.mock.calls[1];
    expect(String(formInit.body)).toBe("username=admin&password=x+y");
    expect(formInit.headers["Content-Type"]).toBeUndefined();
  });

  it("turns FastAPI error bodies into readable ApiErrors", async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: "Alert already reviewed" }, 409));
    await expect(api("/feedback", { method: "POST" })).rejects.toMatchObject({ status: 409, message: "Alert already reviewed" });

    fetchMock.mockResolvedValueOnce(json({ detail: [{ msg: "Input should be greater than 0" }, { msg: "Field required" }] }, 422));
    await expect(api("/score", { method: "POST" })).rejects.toMatchObject({
      status: 422,
      message: "Input should be greater than 0; Field required",
    });

    fetchMock.mockResolvedValueOnce(new Response("<html>oops</html>", { status: 500 }));
    await expect(api("/x")).rejects.toMatchObject({ status: 500, message: "Request failed (HTTP 500)" });
  });

  it("reports an unreachable server as status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await api("/health").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, message: "Cannot reach the server" });
  });

  it("signs the user out on a 401 while a token is stored", async () => {
    const handler = vi.fn();
    onUnauthorized(handler);
    setToken("expired");
    reply({ detail: "Could not validate credentials" }, 401);
    await expect(api("/alerts")).rejects.toMatchObject({ status: 401 });
    expect(getToken()).toBeNull();
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not sign out on a 401 without a token (a failed login)", async () => {
    const handler = vi.fn();
    onUnauthorized(handler);
    reply({ detail: "Incorrect username or password" }, 401);
    await expect(api("/auth/login", { method: "POST", form: { username: "a", password: "b" } })).rejects.toMatchObject({
      status: 401,
      message: "Incorrect username or password",
    });
    expect(handler).not.toHaveBeenCalled();
  });
});
