import { afterEach, vi } from "vitest";
import { api, ApiError, configureApiAuth, configureApiUnauthorized } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  configureApiAuth(async () => null);
  configureApiUnauthorized(() => undefined);
});

test("auth configurator accepts an async token boundary", async () => {
  const getter = vi.fn(async () => "session-token");
  configureApiAuth(getter);
  expect(await getter()).toBe("session-token");
});

test("ApiError exposes safe problem details", () => {
  const error = new ApiError({ type: "about:blank", title: "Denied", status: 403, detail: "Not allowed" });
  expect(error.message).toBe("Not allowed");
  expect(error.problem.status).toBe(403);
});

test("notifies the auth boundary on an unauthorized API response", async () => {
  const unauthorized = vi.fn();
  configureApiUnauthorized(unauthorized);
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Session expired" }), { status: 401, headers: { "Content-Type": "application/json" } })));
  await expect(api.getHistory()).rejects.toBeInstanceOf(ApiError);
  expect(unauthorized).toHaveBeenCalledOnce();
});

test("turns FastAPI validation details into an actionable message", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: [{ loc: ["body", "document_expiration"], msg: "Input should be a valid date" }] }), { status: 422, headers: { "Content-Type": "application/json" } })));
  await expect(api.submitManualVerification({} as never)).rejects.toMatchObject({
    message: "document_expiration: Input should be a valid date",
    problem: { status: 422 },
  });
});

test("surfaces field errors from the API problem response", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ title: "Validation Failed", detail: "Request validation failed", errors: [{ location: "body.phone", code: "string_too_short", message: "String should have at least 7 characters" }] }), { status: 422, headers: { "Content-Type": "application/problem+json" } })));
  await expect(api.submitManualVerification({} as never)).rejects.toMatchObject({
    message: "phone: String should have at least 7 characters",
    problem: { status: 422 },
  });
});

test("normalizes snake_case history pages and lookup tokens", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: "event-1", pet: { id: "pet-1", name: "Pip", species: "cat", record_number: "HC-1" }, event_type: "adoption", effective_at: "2026-01-02T12:00:00Z", source_shelter: { id: "s-1", name: "Harbor" }, reason_category: "Adoption", factual_note: "Signed handoff", corrects_event_id: null }], next_cursor: "cursor-2" }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ token: "opaque", qr_payload: "fido:lookup:opaque", expires_at: "2026-01-02T12:05:00Z" }), { status: 201 }));
  vi.stubGlobal("fetch", fetchMock);
  const history = await api.getHistory();
  expect(history.nextCursor).toBe("cursor-2");
  expect(history.items[0]).toEqual(expect.objectContaining({ eventType: "adoption", effectiveAt: "2026-01-02T12:00:00Z", sourceShelter: { id: "s-1", name: "Harbor" } }));
  expect(history.items[0].pet.recordNumber).toBe("HC-1");
  await expect(api.createLookupToken()).resolves.toEqual({ token: "fido:lookup:opaque", expiresAt: "2026-01-02T12:05:00Z" });
});

test("normalizes pet, access-log, and dispute pages", async () => {
  const pet = { id: "pet-1", shelter_id: "s-1", record_number: "HC-1", name: "Pip", species: "cat", breed_description: "Shorthair", sex: "female", approximate_birth_date: "2024-01-01", color: "gray", altered: true, lifecycle_state: "available" };
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ items: [pet], next_cursor: null }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ shelter: { id: "s-1", name: "Harbor" }, accessed_at: "2026-01-02T12:00:00Z", session_expires_at: "2026-01-02T12:30:00Z" }], next_cursor: null }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: "d-1", event_id: "e-1", owner_reason: "Date is inaccurate", status: "open", created_at: "2026-01-03T12:00:00Z" }], next_cursor: null }), { status: 200 })));
  const pets = await api.getPets("s-1");
  expect(pets.items[0]).toEqual(expect.objectContaining({ shelterId: "s-1", recordNumber: "HC-1", breedDescription: "Shorthair", approximateBirthDate: "2024-01-01" }));
  const access = await api.getAccessLog();
  expect(access.items[0]).toEqual(expect.objectContaining({ shelterName: "Harbor", accessedAt: "2026-01-02T12:00:00Z" }));
  const disputes = await api.getDisputes();
  expect(disputes.items[0]).toEqual(expect.objectContaining({ eventId: "e-1", reason: "Date is inaccurate", createdAt: "2026-01-03T12:00:00Z" }));
});

test("redeems a pass then normalizes the authorized history response", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ session_id: "session-1", expires_at: "2026-01-02T12:30:00Z" }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ person: { display_name: "Maya Carter", verification: "approved" }, items: [{ id: "event-1", pet: { id: "pet-1", name: "Pip", species: "cat", record_number: "HC-1" }, event_type: "adoption", effective_at: "2026-01-01T12:00:00Z", source_shelter: { id: "s-1", name: "Harbor" } }], next_cursor: null }), { status: 200 })));
  const session = await api.redeemLookup("fido:lookup:long-enough-owner-token-value");
  expect(session).toEqual(expect.objectContaining({ id: "session-1", personDisplayName: "Maya Carter", expiresAt: "2026-01-02T12:30:00Z" }));
  expect(session.history[0].pet.recordNumber).toBe("HC-1");
});

test("serializes pet mutations to the backend snake_case contract", async () => {
  const responsePet = { id: "pet-9", shelter_id: "s-1", record_number: "HC-9", name: "Pip", species: "cat", breed_description: "Shorthair", sex: "female", altered: false, lifecycle_state: "available" };
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>().mockResolvedValue(new Response(JSON.stringify(responsePet), { status: 201 }));
  vi.stubGlobal("fetch", fetchMock);
  await api.createPet("s-1", { recordNumber: "HC-9", name: "Pip", species: "cat", breedDescription: "Shorthair", sex: "female", altered: false, lifecycleState: "available" });
  const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
  expect(body).toEqual(expect.objectContaining({ record_number: "HC-9", breed_description: "Shorthair", lifecycle_state: "available" }));
  expect(body).not.toHaveProperty("recordNumber");
});

test("serializes custody creation through the authorized lookup session", async () => {
  const wireEvent = { id: "e-2", pet: { id: "11111111-1111-4111-8111-111111111111", name: "Pip", species: "cat", record_number: "HC-9" }, event_type: "adoption", effective_at: "2026-01-02T12:00:00Z", source_shelter: { id: "s-1", name: "Harbor" } };
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>().mockResolvedValue(new Response(JSON.stringify(wireEvent), { status: 201 }));
  vi.stubGlobal("fetch", fetchMock);
  await api.createCustodyEvent({ lookupSessionId: "session-1", petId: "11111111-1111-4111-8111-111111111111", eventType: "adoption", effectiveAt: "2026-01-02T12:00:00Z", sourceReference: "AG-92" }, "idempotency-1");
  const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
  expect(body).toEqual(expect.objectContaining({ lookup_session_id: "session-1", pet_id: "11111111-1111-4111-8111-111111111111", event_type: "adoption", source_reference: "AG-92" }));
  expect(body).not.toHaveProperty("person_id");
  expect(body).not.toHaveProperty("shelter_id");
});
