import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { AuthProvider } from "./AuthContext";

afterEach(() => vi.unstubAllEnvs());

test("fails closed when Clerk is not configured and demo mode is not explicit", () => {
  vi.stubEnv("VITE_CLERK_PUBLISHABLE_KEY", "");
  vi.stubEnv("VITE_USE_DEMO_DATA", "false");
  render(<QueryClientProvider client={new QueryClient()}><AuthProvider><p>protected content</p></AuthProvider></QueryClientProvider>);
  expect(screen.getByRole("alert")).toHaveTextContent("A Clerk publishable key is required");
  expect(screen.queryByText("protected content")).not.toBeInTheDocument();
});

test("allows the local session only when demo mode is explicit", () => {
  vi.stubEnv("VITE_CLERK_PUBLISHABLE_KEY", "");
  vi.stubEnv("VITE_USE_DEMO_DATA", "true");
  render(<QueryClientProvider client={new QueryClient()}><AuthProvider><p>demo content</p></AuthProvider></QueryClientProvider>);
  expect(screen.getByText("demo content")).toBeInTheDocument();
});
