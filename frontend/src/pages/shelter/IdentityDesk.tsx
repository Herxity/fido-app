import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Fingerprint } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../../api/client";
import type { IdentityReview, ManualVerificationInput } from "../../api/types";
import { LicenseScanner } from "../../identity/LicenseScanner";
import type { ParsedLicense } from "../../identity/licenseScan";
import { EmptyState, ErrorState, LoadingState, StatusPill } from "../../components/States";

const emptyEvidence: ManualVerificationInput = {
  verificationCode: "", fullName: "", dateOfBirth: "", addressLine1: "", addressLine2: "", city: "", region: "", postalCode: "", country: "US", phone: "", governmentIdLast4: "", documentType: "driving_license", documentNumber: "", issuingJurisdiction: "", documentExpiration: "", physicalDocumentExamined: false, likenessMatches: false, ownerConsented: false,
};

const labels: Record<string, string> = {
  same_document: "same document", same_name_and_dob: "same name + birth date", same_address_and_dob: "same address + birth date", same_last4_name_and_dob: "same ID last four + name + birth date", similar_name: "similar name", similar_address: "similar address",
};

function ReviewRow({ review }: { review: IdentityReview }) {
  const queryClient = useQueryClient();
  const [explanation, setExplanation] = useState("");
  const resolve = useMutation({ mutationFn: ({ decision, personId }: { decision: "link_existing" | "approve_new" | "decline"; personId?: string }) => api.resolveIdentityReview(review.id, decision, explanation, personId), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["identity-reviews"] }) });
  return <article className="review-case"><header><div><StatusPill tone="attention">{review.classification}</StatusPill><h3>{review.submittedName}</h3><small>Submitted {new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(review.createdAt))}</small></div>{review.requiresSecondReviewer && <span className="second-reviewer"><AlertTriangle size={16} /> Another employee must decide</span>}</header>
    <div className="candidate-list">{review.candidates.map((candidate) => <div className="candidate" key={candidate.personId}><div><strong>{candidate.displayName}</strong><span>{candidate.evidence.map((item) => labels[item] || item).join(" · ")}</span></div><data value={candidate.confidence}>{candidate.confidence}% evidence confidence</data>{!review.requiresSecondReviewer && <button className="button secondary" disabled={resolve.isPending || explanation.trim().length < 3} onClick={() => resolve.mutate({ decision: "link_existing", personId: candidate.personId })}>Link this person</button>}</div>)}</div>
    <label htmlFor={`explanation-${review.id}`}>Reviewer explanation</label><textarea id={`explanation-${review.id}`} rows={3} value={explanation} onChange={(event) => setExplanation(event.target.value)} minLength={3} maxLength={1000} placeholder="Describe the physical evidence and why this decision is appropriate." />
    {!review.requiresSecondReviewer && <div className="form-actions"><button className="button secondary" disabled={resolve.isPending || explanation.trim().length < 3} onClick={() => resolve.mutate({ decision: "decline" })}>Decline</button><button className="button primary" disabled={resolve.isPending || explanation.trim().length < 3} onClick={() => resolve.mutate({ decision: "approve_new" })}>Confirm separate person</button></div>}{resolve.isError && <p className="form-error" role="alert">The review was not saved. Refresh and try again.</p>}
  </article>;
}

export function IdentityDesk() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ManualVerificationInput>(emptyEvidence);
  const reviews = useQuery({ queryKey: ["identity-reviews"], queryFn: api.getIdentityReviews });
  const submit = useMutation({ mutationFn: api.submitManualVerification, onSuccess: () => { setForm(emptyEvidence); void queryClient.invalidateQueries({ queryKey: ["identity-reviews"] }); } });
  const update = <K extends keyof ManualVerificationInput>(key: K, value: ManualVerificationInput[K]) => setForm((current) => ({ ...current, [key]: value }));
  const parsed = (license: ParsedLicense) => setForm((current) => ({ ...current, ...license, documentType: "driving_license" }));
  const onSubmit = (event: FormEvent) => { event.preventDefault(); submit.mutate(form); };

  return <div className="page-stack identity-desk"><header className="page-header"><div><p className="eyebrow">Identity evidence desk</p><h1>Verify an owner in person</h1><p>Compare the person, printed card, and parsed fields. The system reconciles records; it does not judge adoption suitability.</p></div><StatusPill>Two-person review for ambiguity</StatusPill></header>
    <LicenseScanner onParsed={parsed} />
    <form className="form-panel identity-form" onSubmit={onSubmit}><div className="section-heading"><div><p className="eyebrow">Evidence ledger</p><h2>Review every captured field</h2></div><Fingerprint /></div>
      <div className="field-grid"><div><label htmlFor="verification-code">Owner verification code</label><input id="verification-code" value={form.verificationCode} onChange={(event) => update("verificationCode", event.target.value)} minLength={16} maxLength={80} required autoComplete="off" /></div><div><label htmlFor="full-name">Full legal name</label><input id="full-name" value={form.fullName} onChange={(event) => update("fullName", event.target.value)} maxLength={200} required /></div></div>
      <div className="field-grid"><div><label htmlFor="dob">Date of birth</label><input id="dob" type="date" value={form.dateOfBirth} onChange={(event) => update("dateOfBirth", event.target.value)} required /></div><div><label htmlFor="phone">Phone, if independently confirmed</label><input id="phone" type="tel" value={form.phone} onChange={(event) => update("phone", event.target.value)} maxLength={30} /></div></div>
      <div><label htmlFor="address-line1">Address</label><input id="address-line1" value={form.addressLine1} onChange={(event) => update("addressLine1", event.target.value)} maxLength={200} required /></div>
      <div className="field-grid"><div><label htmlFor="city">City</label><input id="city" value={form.city} onChange={(event) => update("city", event.target.value)} maxLength={100} required /></div><div><label htmlFor="region">State / province</label><input id="region" value={form.region} onChange={(event) => update("region", event.target.value)} maxLength={100} required /></div><div><label htmlFor="postal">Postal code</label><input id="postal" value={form.postalCode} onChange={(event) => update("postalCode", event.target.value)} maxLength={20} required /></div><div><label htmlFor="country">Country code</label><input id="country" value={form.country} onChange={(event) => update("country", event.target.value.toUpperCase())} minLength={2} maxLength={2} required /></div></div>
      <div className="field-grid"><div><label htmlFor="document-type">Document type</label><select id="document-type" value={form.documentType} onChange={(event) => update("documentType", event.target.value as ManualVerificationInput["documentType"])}><option value="driving_license">Driver’s license</option><option value="state_id">State ID</option><option value="passport">Passport</option></select></div><div><label htmlFor="document-number">Document number</label><input id="document-number" value={form.documentNumber} onChange={(event) => update("documentNumber", event.target.value)} maxLength={80} required /></div><div><label htmlFor="issuer">Issuing jurisdiction</label><input id="issuer" value={form.issuingJurisdiction} onChange={(event) => update("issuingJurisdiction", event.target.value)} maxLength={100} required /></div><div><label htmlFor="expiration">Expiration</label><input id="expiration" type="date" value={form.documentExpiration} onChange={(event) => update("documentExpiration", event.target.value)} required /></div></div>
      <div><label htmlFor="last-four">Government ID last four, if independently provided</label><input id="last-four" inputMode="numeric" pattern="[0-9]{4}" value={form.governmentIdLast4} onChange={(event) => update("governmentIdLast4", event.target.value.replace(/\D/g, "").slice(0, 4))} /></div>
      <fieldset className="attestations"><legend>Required physical checks</legend><label className="check-control"><input type="checkbox" checked={form.physicalDocumentExamined} onChange={(event) => update("physicalDocumentExamined", event.target.checked)} required /> I examined the physical document and its security features.</label><label className="check-control"><input type="checkbox" checked={form.likenessMatches} onChange={(event) => update("likenessMatches", event.target.checked)} required /> The photograph reasonably matches the person present.</label><label className="check-control"><input type="checkbox" checked={form.ownerConsented} onChange={(event) => update("ownerConsented", event.target.checked)} required /> The owner consented to identity reconciliation.</label></fieldset>
      {submit.isError && <p className="form-error" role="alert">Verification was not submitted. Check the code, expiration, and required fields.</p>}{submit.isSuccess && <div className="submission-result" role="status"><CheckCircle2 /><div><strong>{submit.data.classification === "new_identity" || submit.data.classification === "exact_existing" ? "Identity reconciled" : "Second review required"}</strong><span>{submit.data.classification.replaceAll("_", " ")}</span></div></div>}
      <div className="form-actions"><button className="button primary" disabled={submit.isPending}>{submit.isPending ? "Reconciling…" : "Submit verification"}</button></div>
    </form>
    <section className="queue review-ledger" aria-labelledby="review-heading"><div className="section-heading"><div><p className="eyebrow">Ambiguous matches</p><h2 id="review-heading">Second-review queue</h2></div></div>{reviews.isLoading ? <LoadingState /> : reviews.isError ? <ErrorState retry={() => void reviews.refetch()} /> : reviews.data?.items.length ? reviews.data.items.map((review) => <ReviewRow review={review} key={review.id} />) : <EmptyState title="No identity matches need review">Fuzzy and conflicting evidence will appear here without exposing raw ID numbers.</EmptyState>}</section>
  </div>;
}
