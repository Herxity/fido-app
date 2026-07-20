import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { HistoryEntry } from "../../api/types";
import { CareTimeline } from "../../components/CareTimeline";
import { EmptyState, ErrorState, LoadingState, StatusPill } from "../../components/States";

export function OwnerHistory() {
  const navigate = useNavigate();
  const history = useQuery({ queryKey: ["owner-history"], queryFn: api.getHistory });
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
