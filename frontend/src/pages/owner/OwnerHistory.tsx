import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useOutletContext } from "react-router-dom";
import { api } from "../../api/client";
import type { HistoryEntry, Viewer } from "../../api/types";
import { CareTimeline } from "../../components/CareTimeline";
import { EmptyState, ErrorState, LoadingState, StatusPill } from "../../components/States";
import { ShelterVerificationRequest } from "../../identity/ShelterVerificationRequest";

export function OwnerHistory() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { viewer } = useOutletContext<{ viewer: Viewer }>();
  const identityApproved = viewer.identityStatus === "approved";
  const history = useQuery({ queryKey: ["owner-history"], queryFn: api.getHistory, enabled: identityApproved });
  if (!identityApproved) return <div className="page-stack narrow">
    <header className="page-header"><div><p className="eyebrow">Your factual record</p><h1>Verify your identity</h1><p>Before Fido can connect or display care history, confirm that this account belongs to you.</p></div><StatusPill tone="attention">{viewer.identityStatus === "pending" ? "Verification pending" : "Identity required"}</StatusPill></header>
    <ShelterVerificationRequest onComplete={() => { void queryClient.invalidateQueries({ queryKey: ["me"] }); }} />
    <div className="neutral-callout"><strong>Your new account is ready.</strong><span>There is no connection problem. Care history stays closed until a shelter verifies your physical ID and any possible duplicate is reconciled.</span></div>
  </div>;
  if (history.isLoading) return <LoadingState />;
  if (history.isError) return <ErrorState retry={() => void history.refetch()} />;
  const entries = history.data?.items ?? [];
  return <div className="page-stack">
    <header className="page-header"><div><p className="eyebrow">Your factual record</p><h1>Care history</h1><p>Each entry names the shelter that recorded it. Fido does not score or judge this history.</p></div><StatusPill tone="positive">Identity verified</StatusPill></header>
    <section className="ledger" aria-labelledby="journey-title"><div className="section-heading"><div><p className="eyebrow">Cross-shelter ledger</p><h2 id="journey-title">Care journey</h2></div><p>{entries.length} recorded {entries.length === 1 ? "event" : "events"}</p></div>
      {entries.length ? <CareTimeline entries={entries} onDispute={(entry: HistoryEntry) => navigate(`/owner/disputes/new?event=${entry.id}`)} /> : <EmptyState title="No history recorded yet">When a participating shelter records a handoff, it will appear here with its source.</EmptyState>}
    </section>
  </div>;
}
