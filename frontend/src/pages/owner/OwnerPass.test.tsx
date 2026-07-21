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
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: vi.fn().mockResolvedValue(undefined) } });
  vi.mocked(api.createLookupToken).mockResolvedValue({ token: "fido:lookup:local-test-pass", expiresAt: new Date(Date.now() + 300_000).toISOString() });
});

test("shows and copies the generated owner pass code", async () => {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><OwnerPass /></QueryClientProvider>);

  fireEvent.click(screen.getByRole("button", { name: "Create shelter pass" }));

  expect(await screen.findByDisplayValue("fido:lookup:local-test-pass")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Copy code" }));
  await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith("fido:lookup:local-test-pass"));
  expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
});
