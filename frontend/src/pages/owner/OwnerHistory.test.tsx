import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { api } from "../../api/client";
import type { Viewer } from "../../api/types";
import { OwnerHistory } from "./OwnerHistory";

test("shows identity onboarding instead of requesting protected history for a new owner", () => {
  const getHistory = vi.spyOn(api, "getHistory");
  const viewer: Viewer = { id: "owner_1", name: "New owner", email: "", mode: "owner", identityStatus: "unverified" };
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/owner/history"]}><Routes><Route element={<Outlet context={{ viewer }} />}><Route path="/owner/history" element={<OwnerHistory />} /></Route></Routes></MemoryRouter></QueryClientProvider>);

  expect(screen.getByRole("heading", { name: "Verify your identity" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Verify identity" })).toBeInTheDocument();
  expect(screen.getByText(/There is no connection problem/)).toBeInTheDocument();
  expect(getHistory).not.toHaveBeenCalled();
});
