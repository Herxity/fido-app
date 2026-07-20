import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import { EmptyState, ErrorState, LoadingState, StatusPill } from "../../components/States";

export function ShelterDisputes() {
  const [correcting, setCorrecting] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const queryClient = useQueryClient();
  const disputes = useQuery({ queryKey: ["disputes"], queryFn: api.getDisputes });
  const correction = useMutation({ mutationFn: ({ eventId, factualNote }: { eventId: string; factualNote: string }) => api.createCorrection(eventId, { factualNote, effectiveAt: new Date().toISOString() }, crypto.randomUUID()), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["disputes"] }); setCorrecting(null); setNote(""); } });
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">Corrections and context</p><h1>Dispute review</h1><p>Respond with factual context. Resolutions append to the ledger; they never erase the source entry.</p></div></header><section className="queue">
    {disputes.isLoading ? <LoadingState /> : disputes.isError ? <ErrorState retry={() => void disputes.refetch()} /> : !disputes.data?.items.length ? <EmptyState title="No disputes need review">New owner correction requests will appear here.</EmptyState> : disputes.data.items.map((item) => <article className="dispute-row" key={item.id}><div><StatusPill tone="attention">{item.status.replace("_", " ")}</StatusPill><h2>Correction request</h2><p>{item.reason}</p><small>Received {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(item.createdAt))}</small>{correcting === item.id && <form className="correction-form" onSubmit={(event) => { event.preventDefault(); if (note.trim().length >= 10) correction.mutate({ eventId: item.eventId, factualNote: note.trim() }); }}><label htmlFor={`correction-${item.id}`}>Appended factual correction</label><textarea id={`correction-${item.id}`} rows={4} value={note} onChange={(event) => setNote(event.target.value)} minLength={10} maxLength={1000} required />{correction.isError && <p className="form-error" role="alert">The correction was not appended. Try again.</p>}<div className="form-actions"><button type="button" className="button secondary" onClick={() => setCorrecting(null)}>Cancel</button><button className="button primary" disabled={correction.isPending || note.trim().length < 10}>{correction.isPending ? "Appending…" : "Append correction"}</button></div></form>}</div>{correcting !== item.id && <button className="button secondary" onClick={() => setCorrecting(item.id)}>Review and correct</button>}</article>)}
  </section></div>;
}
