import { AlertCircle, ArrowRight, FilePenLine } from "lucide-react";
import type { HistoryEntry } from "../api/types";
import { StatusPill } from "./States";

const labels: Record<HistoryEntry["eventType"], string> = {
  adoption: "Adopted", return_from_adoption: "Returned to shelter", owner_surrender: "Owner surrender", reclaim_by_owner: "Reclaimed by owner", transfer_in: "Transferred in", transfer_out: "Transferred out", foster_start: "Foster care began", foster_end: "Foster care ended", correction: "Record corrected"
};

export function CareTimeline({ entries, onDispute }: { entries: HistoryEntry[]; onDispute?: (entry: HistoryEntry) => void }) {
  return <ol className="care-timeline" aria-label="Care journey">
    {entries.map((entry) => <li key={entry.id} className={`journey-event ${entry.eventType === "correction" ? "is-correction" : ""}`}>
      <span className="journey-pin" aria-hidden="true">{entry.eventType === "correction" ? <FilePenLine size={16} /> : <ArrowRight size={16} />}</span>
      <article>
        <div className="event-heading"><div><p className="event-date">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(entry.effectiveAt))}</p><h3>{labels[entry.eventType]} · {entry.pet.name}</h3></div><span className="source-stamp">{entry.sourceShelter.name}</span></div>
        <p className="pet-ref">{entry.pet.species} · record {entry.pet.recordNumber}</p>
        {entry.reasonCategory && <p><strong>Recorded reason:</strong> {entry.reasonCategory}</p>}
        {entry.factualNote && <p>{entry.factualNote}</p>}
        <div className="event-links">
          {entry.correctionOfId && <StatusPill tone="attention">Corrects an earlier entry</StatusPill>}
          {entry.disputeStatus && <StatusPill tone="attention"><AlertCircle size={13} /> Dispute {entry.disputeStatus.replace("_", " ")}</StatusPill>}
          {onDispute && !entry.correctionOfId && <button className="text-button" onClick={() => onDispute(entry)}>Something is inaccurate</button>}
        </div>
      </article>
    </li>)}
  </ol>;
}
