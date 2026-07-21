import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, test, vi } from "vitest";
import { api } from "../../api/client";
import { OwnerPass } from "./OwnerPass";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, api: { ...actual.api, createLookupToken: vi.fn() } };
});

beforeEach(() => {
  window.sessionStorage.clear();
  vi.mocked(api.createLookupToken).mockResolvedValue({ token: "fido:lookup:local-test-pass", expiresAt: new Date(Date.now() + 300_000).toISOString() });
});

test("saves a generated pass for the local shelter shortcut", async () => {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><OwnerPass /></QueryClientProvider>);

  fireEvent.click(screen.getByRole("button", { name: "Create shelter pass" }));

  expect(await screen.findByText(/Local test pass saved/)).toBeInTheDocument();
  await waitFor(() => expect(JSON.parse(window.sessionStorage.getItem("fido:local-owner-pass") || "null")).toMatchObject({ token: "fido:lookup:local-test-pass" }));
});
