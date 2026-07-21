import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, test, vi } from "vitest";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { api } from "../../api/client";
import { OwnerLookup } from "./OwnerLookup";
import type { Viewer } from "../../api/types";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, api: { ...actual.api, redeemLookup: vi.fn() } };
});

const viewer: Viewer = { id: "staff-1", name: "Casey Reviewer", email: "casey@example.test", mode: "shelter", identityStatus: "approved", shelter: { id: "shelter-1", name: "Harbor County Shelter", role: "shelter_staff" } };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.redeemLookup).mockResolvedValue({ id: "lookup-1", personDisplayName: "Maya Owner", expiresAt: new Date(Date.now() + 1_800_000).toISOString(), history: [] });
});

test("redeems a pasted owner pass code", async () => {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/shelter/lookup"]}><Routes><Route element={<Outlet context={{ viewer }} />}><Route path="/shelter/lookup" element={<OwnerLookup />} /></Route></Routes></MemoryRouter></QueryClientProvider>);

  fireEvent.change(screen.getByLabelText("Owner pass code"), { target: { value: "fido:lookup:local-test-pass" } });
  fireEvent.click(screen.getByRole("button", { name: "Open factual history" }));

  await waitFor(() => expect(api.redeemLookup).toHaveBeenCalledWith("fido:lookup:local-test-pass"));
  expect(await screen.findByRole("heading", { name: "Maya Owner" })).toBeInTheDocument();
});
