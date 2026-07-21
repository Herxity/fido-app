export type IdentityStatus = "unverified" | "pending" | "approved" | "declined" | "needs_review";
export type CustodyEventType = "adoption" | "return_from_adoption" | "owner_surrender" | "reclaim_by_owner" | "transfer_in" | "transfer_out" | "foster_start" | "foster_end" | "correction";
export type DisputeStatus = "open" | "shelter_review" | "platform_review" | "resolved" | "rejected";

export interface Viewer {
  id: string;
  name: string;
  email: string;
  mode: "owner" | "shelter";
  identityStatus: IdentityStatus;
  shelter?: { id: string; name: string; role: "shelter_admin" | "shelter_staff" | "shelter_read_only" };
}

export interface PetSummary {
  id: string;
  shelterId: string;
  recordNumber: string;
  name: string;
  species: string;
  breedDescription: string;
  sex: string;
  approximateBirthDate?: string;
  color?: string;
  altered?: boolean;
  lifecycleState: "available" | "adopted" | "foster" | "transferred" | "inactive";
}

export interface HistoryEntry {
  id: string;
  pet: Pick<PetSummary, "id" | "name" | "species" | "recordNumber">;
  eventType: CustodyEventType;
  effectiveAt: string;
  sourceShelter: { id: string; name: string };
  reasonCategory?: string;
  factualNote?: string;
  correctionOfId?: string;
  disputeStatus?: DisputeStatus;
}

export interface LookupTokenResponse { token: string; expiresAt: string; }
export interface LookupSession { id: string; personDisplayName: string; expiresAt: string; history: HistoryEntry[]; }
export interface AccessLogEntry { id: string; shelterName: string; staffDisplayName: string; accessedAt: string; }
export interface Dispute { id: string; eventId: string; reason: string; status: DisputeStatus; createdAt: string; resolutionSummary?: string; }
export interface ManualVerificationInput {
  verificationCode: string; fullName: string; dateOfBirth: string;
  addressLine1: string; addressLine2?: string; city: string; region: string; postalCode: string; country: string;
  phone?: string; governmentIdLast4?: string; documentType: "driving_license" | "state_id" | "passport";
  documentNumber: string; issuingJurisdiction: string; documentExpiration: string;
  physicalDocumentExamined: boolean; likenessMatches: boolean; ownerConsented: boolean;
}
export interface IdentityCandidate { personId: string; displayName: string; classification: "exact" | "fuzzy"; confidence: number; evidence: string[]; }
export interface IdentityReview { id: string; submittedName: string; classification: "fuzzy" | "conflict"; createdAt: string; requiresSecondReviewer: boolean; candidates: IdentityCandidate[]; }
export interface CursorPage<T> { items: T[]; nextCursor?: string; }

export interface ApiProblem {
  type: string;
  title: string;
  status: number;
  detail: string;
  requestId?: string;
  errors?: Record<string, string[]>;
}
