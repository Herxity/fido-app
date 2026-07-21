import { useQuery } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client";
import type { Viewer } from "../../api/types";
import { ShelterVerificationRequest } from "../../identity/ShelterVerificationRequest";
import { EmptyState, ErrorState, LoadingState, StatusPill } from "../../components/States";

export function OwnerAccount() {
  const { viewer } = useOutletContext<{ viewer: Viewer }>();
  const accesses = useQuery({ queryKey: ["access-log"], queryFn: api.getAccessLog });
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">Privacy and identity</p><h1>Your account</h1><p>Review identity status and every shelter access to your history.</p></div></header>
    {viewer.identityStatus !== "approved" && <ShelterVerificationRequest onComplete={() => undefined} />}
    <section className="ledger"><div className="section-heading"><div><p className="eyebrow">Audit trail</p><h2>Who viewed my history</h2></div></div>
      {accesses.isLoading ? <LoadingState label="Loading access log…" /> : accesses.isError ? <ErrorState retry={() => void accesses.refetch()} /> : !accesses.data?.items.length ? <EmptyState title="No shelter has viewed your history">Authorized shelter lookups will be listed here.</EmptyState> : <ul className="access-list">{accesses.data.items.map((entry) => <li key={entry.id}><div><strong>{entry.shelterName}</strong><span>{entry.staffDisplayName}</span></div><div><StatusPill>Authorized pass</StatusPill><time>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(entry.accessedAt))}</time></div></li>)}</ul>}
    </section>
  </div>;
}
