import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { HealthBadge } from "./HealthBadge";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, api: vi.fn() };
});

import { api } from "../api/client";
const apiMock = vi.mocked(api);

beforeEach(() => {
  apiMock.mockReset();
});

describe("HealthBadge", () => {
  it("shows a green status when the API and database are up", async () => {
    apiMock.mockResolvedValue({ status: "ok", db: "ok" });
    render(<HealthBadge />);
    expect(screen.getByRole("status")).toHaveTextContent("Checking API");
    expect(await screen.findByText("API ok, database ok")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveClass("health-ok");
  });

  it("shows a warning when the database is down (HTTP 503)", async () => {
    apiMock.mockRejectedValue(new ApiError(503, "database unreachable"));
    render(<HealthBadge />);
    expect(await screen.findByText("API up, database down")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveClass("health-warn");
  });

  it("shows an error when the API cannot be reached", async () => {
    apiMock.mockRejectedValue(new ApiError(0, "Cannot reach the server"));
    render(<HealthBadge />);
    expect(await screen.findByText("API unreachable")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveClass("health-bad");
  });
});
