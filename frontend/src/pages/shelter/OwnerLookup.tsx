import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { z } from "zod";
import { FlaskConical } from "lucide-react";
import { api } from "../../api/client";
import { CareTimeline } from "../../components/CareTimeline";
import { StatusPill } from "../../components/States";
import { CustodyEventForm } from "./CustodyEventForm";
import type { Viewer } from "../../api/types";

const schema = z.object({ token: z.string().trim().min(8, "Enter or scan the full owner pass.") });
type Form = z.infer<typeof schema>;
export function OwnerLookup() {
  const [recording, setRecording] = useState(false);
  const { viewer } = useOutletContext<{ viewer: Viewer }>();
  const localTesting = import.meta.env.DEV && import.meta.env.VITE_DEPLOYMENT_STAGE !== "production";
  const lookup = useMutation({ mutationFn: ({ token }: Form) => api.redeemLookup(token), onSuccess: () => window.sessionStorage.removeItem("fido:local-owner-pass") });
  const { register, handleSubmit, setError, setValue, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema) });
  const useLatestLocalPass = () => {
    try {
      const saved = JSON.parse(window.sessionStorage.getItem("fido:local-owner-pass") || "null") as { token?: unknown; expiresAt?: unknown } | null;
      const candidate = schema.safeParse({ token: saved?.token });
      if (!candidate.success || typeof saved?.expiresAt !== "string" || new Date(saved.expiresAt).getTime() <= Date.now()) {
        setError("token", { message: "No active local owner pass was found. Generate a new pass in the owner view first." });
        return;
      }
      setValue("token", candidate.data.token, { shouldValidate: true });
      lookup.mutate(candidate.data);
    } catch {
      setError("token", { message: "The saved local pass could not be read. Generate a new owner pass and try again." });
    }
  };
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">Owner-present lookup</p><h1>Scan a shelter pass</h1><p>The owner must generate a fresh pass while present. A redeemed session is limited to this shelter.</p></div></header>
    {!lookup.data ? <form className="lookup-panel" onSubmit={handleSubmit((data) => lookup.mutate(data))}>{localTesting && <div className="local-lookup-shortcut"><div><FlaskConical size={19} /><span><strong>Local testing</strong><small>Use the most recent pass generated in this browser tab.</small></span></div><button type="button" className="button primary" disabled={lookup.isPending} onClick={useLatestLocalPass}>{lookup.isPending ? "Opening…" : "Use latest local pass"}</button></div>}<label htmlFor="pass-token">Scanner or manual fallback</label><div className="scan-input"><input id="pass-token" autoComplete="off" {...register("token")} placeholder="Scan QR or paste pass token" /><button className="button secondary" disabled={lookup.isPending}>{lookup.isPending ? "Checking…" : "Open factual history"}</button></div>{errors.token && <p className="form-error">{errors.token.message}</p>}{lookup.isError && <p className="form-error" role="alert">This pass is invalid, expired, or already used. Ask the owner to generate a new one.</p>}<aside><strong>Privacy check</strong><p>Confirm the owner understands that {viewer.shelter?.name || "this shelter"} will be named in their access log.</p></aside></form> : <><section className="ledger"><div className="section-heading"><div><p className="eyebrow">Authorized factual history</p><h2>{lookup.data.personDisplayName}</h2></div><StatusPill tone="attention">Session expires in 30 min</StatusPill></div><div className="neutral-callout"><strong>No suitability score</strong><span>Review source records in context and follow your shelter’s adoption conversation.</span></div><CareTimeline entries={lookup.data.history} /><div className="form-actions"><button className="button primary" onClick={() => setRecording(true)}>Record owner handoff</button></div></section>{recording && <section className="form-panel" aria-labelledby="handoff-title"><div className="section-heading"><div><p className="eyebrow">Authorized append-only entry</p><h2 id="handoff-title">Record handoff</h2></div></div><CustodyEventForm lookupSessionId={lookup.data.id} onDone={() => setRecording(false)} onCancel={() => setRecording(false)} /></section>}</>}
  </div>;
}
