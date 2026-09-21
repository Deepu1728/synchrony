import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { loginErrorMessage } from "./messages";

describe("loginErrorMessage", () => {
  it.each([
    [401, "Incorrect username or password."],
    [0, "Cannot reach the server. Check that the API is running and try again."],
    [429, "Too many attempts. Wait a moment and try again."],
    [500, "The server had a problem (HTTP 500). Try again in a moment."],
    [503, "The server had a problem (HTTP 503). Try again in a moment."],
  ])("maps HTTP %i to a friendly message", (status, message) => {
    expect(loginErrorMessage(new ApiError(status, "raw detail"))).toBe(message);
  });

  it("passes through other API messages and handles unknown errors", () => {
    expect(loginErrorMessage(new ApiError(422, "Field required"))).toBe("Field required");
    expect(loginErrorMessage(new Error("boom"))).toBe("Something went wrong. Try again.");
    expect(loginErrorMessage("nope")).toBe("Something went wrong. Try again.");
  });
});
