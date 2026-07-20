import { demoAccess, demoDisputes, demoHistory, demoPets, ownerViewer, shelterViewer } from "./demo";
import type { ApiProblem, AccessLogEntry, CursorPage, Dispute, HistoryEntry, LookupSession, LookupTokenResponse, PetSummary, Viewer } from "./types";

const baseUrl = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const demo = import.meta.env.VITE_USE_DEMO_DATA === "true";

type Wire = Record<string, unknown>;
const textValue = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;
const normalizePet = (raw: Wire): PetSummary => ({
  id: textValue(raw.id), shelterId: textValue(raw.shelter_id), recordNumber: textValue(raw.record_number), name: textValue(raw.name), species: textValue(raw.species), breedDescription: textValue(raw.breed_description), sex: textValue(raw.sex), approximateBirthDate: textValue(raw.approximate_birth_date) || undefined, color: textValue(raw.color) || undefined, altered: typeof raw.altered === "boolean" ? raw.altered : undefined, lifecycleState: textValue(raw.lifecycle_state, "inactive") as PetSummary["lifecycleState"]
});
const normalizeHistory = (raw: Wire): HistoryEntry => {
  const pet = (raw.pet || {}) as Wire; const shelter = (raw.source_shelter || {}) as Wire;
  return { id: textValue(raw.id), pet: { id: textValue(pet.id), name: textValue(pet.name), species: textValue(pet.species), recordNumber: textValue(pet.record_number) }, eventType: textValue(raw.event_type) as HistoryEntry["eventType"], effectiveAt: textValue(raw.effective_at), sourceShelter: { id: textValue(shelter.id), name: textValue(shelter.name) }, reasonCategory: textValue(raw.reason_category) || undefined, factualNote: textValue(raw.factual_note) || undefined, correctionOfId: textValue(raw.corrects_event_id) || undefined, disputeStatus: textValue(raw.dispute_status) as HistoryEntry["disputeStatus"] || undefined };
};
const normalizePage = <T>(raw: Wire, item: (value: Wire) => T): CursorPage<T> => ({ items: Array.isArray(raw.items) ? raw.items.map((value) => item(value as Wire)) : [], nextCursor: textValue(raw.next_cursor) || undefined });
const petWire = (input: Partial<Omit<PetSummary, "id" | "shelterId">>) => ({ record_number: input.recordNumber, name: input.name, species: input.species, breed_description: input.breedDescription || null, sex: input.sex || null, approximate_birth_date: input.approximateBirthDate || null, color: input.color || null, altered: input.altered, lifecycle_state: input.lifecycleState });

export class ApiError extends Error {
  constructor(public problem: ApiProblem) { super(problem.detail || problem.title); }
}

type TokenGetter = () => Promise<string | null>;
let getToken: TokenGetter = async () => null;
let onUnauthorized: () => void = () => undefined;
export const configureApiAuth = (getter: TokenGetter) => { getToken = getter; };
export const configureApiUnauthorized = (handler: () => void) => { onUnauthorized = handler; };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Accept: "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers }
  });
  if (!response.ok) {
    if (response.status === 401) onUnauthorized();
    const fallback: ApiProblem = { type: "about:blank", title: "Request failed", status: response.status, detail: "We could not complete that request. Please try again.", requestId: response.headers.get("x-request-id") || undefined };
    let problem = fallback;
    try { problem = { ...fallback, ...(await response.json()) }; } catch { /* preserve safe fallback */ }
    throw new ApiError(problem);
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}

export const api = {
  getMe: async (mode: "owner" | "shelter" = "owner"): Promise<Viewer> => { if (demo) return mode === "owner" ? ownerViewer : shelterViewer; const raw = await request<Wire>("/me"); const shelter = raw.shelter as Wire | undefined; return { id: textValue(raw.user_id), name: textValue(raw.display_name, mode === "shelter" ? "Shelter staff" : "Verified owner"), email: textValue(raw.email), mode: shelter ? "shelter" : "owner", identityStatus: textValue(raw.identity_status, "unverified") as Viewer["identityStatus"], shelter: shelter ? { id: textValue(shelter.id), name: textValue(shelter.name), role: textValue(shelter.role) as NonNullable<Viewer["shelter"]>["role"] } : undefined }; },
  getHistory: async (): Promise<CursorPage<HistoryEntry>> => demo ? { items: demoHistory } : normalizePage(await request<Wire>("/me/history"), normalizeHistory),
  getAccessLog: async (): Promise<CursorPage<AccessLogEntry>> => { if (demo) return { items: demoAccess }; const raw = await request<Wire>("/me/access-log"); return normalizePage(raw, (entry) => { const shelter = (entry.shelter || {}) as Wire; const accessedAt = textValue(entry.accessed_at); return { id: `${textValue(shelter.id, "unknown")}:${accessedAt}`, shelterName: textValue(shelter.name, "Participating shelter"), staffDisplayName: "Authorized shelter staff", accessedAt }; }); },
  createInquiry: (): Promise<{ inquiryId: string; sessionToken: string }> => request("/identity/inquiries", { method: "POST" }),
  createLookupToken: async (): Promise<LookupTokenResponse> => { if (demo) return { token: "fido_demo_7Q2K9M", expiresAt: new Date(Date.now() + 300000).toISOString() }; const raw = await request<Wire>("/me/lookup-tokens", { method: "POST" }); return { token: textValue(raw.qr_payload) || textValue(raw.token), expiresAt: textValue(raw.expires_at) }; },
  redeemLookup: async (token: string): Promise<LookupSession> => { if (demo) return { id: "lookup-1", personDisplayName: "Maya Carter", expiresAt: new Date(Date.now() + 1800000).toISOString(), history: demoHistory }; const redemption = await request<Wire>("/lookups/redeem", { method: "POST", body: JSON.stringify({ token }) }); const id = textValue(redemption.session_id); const history = await request<Wire>(`/lookups/${id}/history`); const person = (history.person || {}) as Wire; return { id, expiresAt: textValue(redemption.expires_at), personDisplayName: textValue(person.display_name, "Verified owner"), history: normalizePage(history, normalizeHistory).items }; },
  getPets: async (shelterId: string): Promise<CursorPage<PetSummary>> => demo ? { items: demoPets } : normalizePage(await request<Wire>(`/shelters/${shelterId}/pets`), normalizePet),
  getPet: async (shelterId: string, petId: string): Promise<PetSummary> => demo ? demoPets.find((pet) => pet.id === petId)! : normalizePet(await request<Wire>(`/shelters/${shelterId}/pets/${petId}`)),
  createPet: async (shelterId: string, input: Omit<PetSummary, "id" | "shelterId">): Promise<PetSummary> => normalizePet(await request<Wire>(`/shelters/${shelterId}/pets`, { method: "POST", body: JSON.stringify(petWire(input)) })),
  updatePet: async (shelterId: string, petId: string, input: Partial<Omit<PetSummary, "id" | "shelterId">>): Promise<PetSummary> => normalizePet(await request<Wire>(`/shelters/${shelterId}/pets/${petId}`, { method: "PATCH", body: JSON.stringify(petWire(input)) })),
  createCustodyEvent: async (input: Record<string, unknown>, idempotencyKey: string): Promise<HistoryEntry> => normalizeHistory(await request<Wire>("/custody-events", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ lookup_session_id: input.lookupSessionId, pet_id: input.petId, event_type: input.eventType, effective_at: input.effectiveAt, source_reference: input.sourceReference || null, reason_category: input.reasonCategory || null, factual_note: input.factualNote || null }) })),
  createCorrection: async (eventId: string, input: { factualNote: string; effectiveAt: string }, idempotencyKey: string): Promise<HistoryEntry> => normalizeHistory(await request<Wire>(`/custody-events/${eventId}/corrections`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ factual_note: input.factualNote, effective_at: input.effectiveAt }) })),
  getDisputes: async (): Promise<CursorPage<Dispute>> => demo ? { items: demoDisputes } : normalizePage(await request<Wire>("/disputes"), (entry) => ({ id: textValue(entry.id), eventId: textValue(entry.event_id), reason: textValue(entry.owner_reason), status: textValue(entry.status) as Dispute["status"], createdAt: textValue(entry.created_at), resolutionSummary: textValue(entry.resolution_summary) || undefined })),
  createDispute: async (eventId: string, reason: string): Promise<Dispute> => { const raw = await request<Wire>("/me/disputes", { method: "POST", body: JSON.stringify({ event_id: eventId, reason }) }); return { id: textValue(raw.id), eventId, reason, status: textValue(raw.status, "open") as Dispute["status"], createdAt: textValue(raw.created_at) }; },
  updateDispute: async (id: string, input: { status: string; resolutionSummary: string }): Promise<Dispute> => { const raw = await request<Wire>(`/disputes/${id}`, { method: "PATCH", body: JSON.stringify({ status: input.status, resolution_summary: input.resolutionSummary }) }); return { id: textValue(raw.id, id), eventId: textValue(raw.event_id), reason: textValue(raw.owner_reason), status: textValue(raw.status) as Dispute["status"], createdAt: textValue(raw.created_at), resolutionSummary: textValue(raw.resolution_summary) || undefined }; }
};
