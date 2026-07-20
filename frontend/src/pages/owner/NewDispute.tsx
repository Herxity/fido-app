import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { api } from "../../api/client";

const schema = z.object({ reason: z.string().trim().min(20, "Add at least 20 characters so the shelter knows what to review.").max(1000) });
type Form = z.infer<typeof schema>;
export function NewDispute() {
  const [params] = useSearchParams(); const eventId = params.get("event") || "";
  const mutation = useMutation({ mutationFn: (data: Form) => api.createDispute(eventId, data.reason) });
  const { register, handleSubmit, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema) });
  if (mutation.isSuccess) return <div className="state success-state"><strong>Your correction request is in review.</strong><span>The source shelter can respond, but the original entry will remain visible for transparency.</span><Link className="button secondary" to="/owner/history">Back to care history</Link></div>;
  return <div className="page-stack narrow"><header className="page-header"><div><p className="eyebrow">Request a correction</p><h1>What needs attention?</h1><p>Describe the factual inaccuracy. Avoid adding sensitive medical or financial information.</p></div></header>
    <form className="form-panel" onSubmit={handleSubmit((data) => mutation.mutate(data))}><label htmlFor="reason">Correction details</label><textarea id="reason" rows={7} {...register("reason")} aria-invalid={Boolean(errors.reason)} aria-describedby="reason-error" />{errors.reason && <p id="reason-error" className="form-error">{errors.reason.message}</p>}{mutation.isError && <p className="form-error" role="alert">The request could not be sent. Try again.</p>}<div className="form-actions"><Link className="button secondary" to="/owner/history">Cancel</Link><button className="button primary" disabled={mutation.isPending}>{mutation.isPending ? "Sending…" : "Submit for review"}</button></div></form>
  </div>;
}
