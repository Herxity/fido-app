import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, test, vi } from "vitest";
import { api } from "../../api/client";
import { IdentityDesk } from "./IdentityDesk";

vi.mock("../../api/client", () => ({ api: { getIdentityReviews: vi.fn(), submitManualVerification: vi.fn(), resolveIdentityReview: vi.fn() } }));

beforeEach(() => {
  vi.mocked(api.getIdentityReviews).mockResolvedValue({ items: [] });
});

test("presents scanner, editable evidence, physical checks, and review queue", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><IdentityDesk /></QueryClientProvider>);

  expect(screen.getByRole("heading", { name: "Verify an owner in person" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open camera" })).toBeInTheDocument();
  expect(screen.getByLabelText("USB or Bluetooth scanner input")).toBeInTheDocument();
  expect(screen.getByLabelText("Owner verification code")).toBeRequired();
  expect(screen.getByLabelText(/physical document and its security features/i)).toBeRequired();
  expect(await screen.findByText("No identity matches need review")).toBeInTheDocument();
});
