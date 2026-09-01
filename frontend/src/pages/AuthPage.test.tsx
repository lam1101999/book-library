import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AuthPage from "./AuthPage";

// mock api module so no real fetch happens
vi.mock("../api", () => ({
  login: vi.fn(), register: vi.fn(), googleLoginUrl: "/api/auth/google",
}));

describe("AuthPage", () => {
  it("renders email and password inputs", () => {
    render(
      <MemoryRouter>
        <AuthPage mode="login" />
      </MemoryRouter>
    );
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
  });
});
