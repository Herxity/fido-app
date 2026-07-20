import type { AccessLogEntry, Dispute, HistoryEntry, PetSummary, Viewer } from "./types";

export const ownerViewer: Viewer = { id: "owner-1", name: "Maya Carter", email: "maya@example.com", mode: "owner", identityStatus: "approved" };
export const shelterViewer: Viewer = { id: "staff-1", name: "Jordan Lee", email: "jordan@harbor.example", mode: "shelter", identityStatus: "approved", shelter: { id: "shelter-1", name: "Harbor County Animal Care", role: "shelter_admin" } };
export const demoPets: PetSummary[] = [
  { id: "pet-1", shelterId: "shelter-1", recordNumber: "HC-2418", name: "Miso", species: "Cat", breedDescription: "Domestic shorthair", sex: "Female", approximateBirthDate: "2022-04-01", color: "Tortoiseshell", altered: true, lifecycleState: "available" },
  { id: "pet-2", shelterId: "shelter-1", recordNumber: "HC-2417", name: "Otis", species: "Dog", breedDescription: "Beagle mix", sex: "Male", approximateBirthDate: "2020-09-12", color: "Tricolor", altered: true, lifecycleState: "foster" },
  { id: "pet-3", shelterId: "shelter-1", recordNumber: "HC-2391", name: "June", species: "Dog", breedDescription: "Shepherd mix", sex: "Female", approximateBirthDate: "2019-02-03", color: "Sable", altered: true, lifecycleState: "adopted" }
];
export const demoHistory: HistoryEntry[] = [
  { id: "evt-3", pet: { id: "pet-3", name: "June", species: "Dog", recordNumber: "HC-2391" }, eventType: "return_from_adoption", effectiveAt: "2025-05-18T14:20:00Z", sourceShelter: { id: "shelter-1", name: "Harbor County Animal Care" }, reasonCategory: "Owner circumstances", factualNote: "Returned after a housing change. Shelter intake completed.", disputeStatus: "open" },
  { id: "evt-2", pet: { id: "pet-3", name: "June", species: "Dog", recordNumber: "HC-2391" }, eventType: "correction", effectiveAt: "2024-11-04T10:15:00Z", sourceShelter: { id: "shelter-2", name: "Meadow Lane Rescue" }, factualNote: "Corrected adoption date from November 3 to November 4.", correctionOfId: "evt-1" },
  { id: "evt-1", pet: { id: "pet-3", name: "June", species: "Dog", recordNumber: "ML-882" }, eventType: "adoption", effectiveAt: "2024-11-04T10:15:00Z", sourceShelter: { id: "shelter-2", name: "Meadow Lane Rescue" }, factualNote: "Adoption agreement signed at shelter." }
];
export const demoAccess: AccessLogEntry[] = [{ id: "access-1", shelterName: "Harbor County Animal Care", staffDisplayName: "Jordan L.", accessedAt: "2025-05-18T13:52:00Z" }];
export const demoDisputes: Dispute[] = [{ id: "disp-1", eventId: "evt-3", reason: "The housing-change note needs more context.", status: "open", createdAt: "2025-05-20T11:30:00Z" }];
