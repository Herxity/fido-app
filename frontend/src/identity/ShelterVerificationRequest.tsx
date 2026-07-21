import { Clipboard, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";

export function ShelterVerificationRequest({ onComplete }: { onComplete: () => void }) {
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");

  const begin = async () => {
    setState("loading");
    setMessage("");
    try {
      const result = await api.createInquiry();
      setCode(result.verificationCode);
      setState("ready");
      onComplete();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "A verification request could not be created.");
      setState("error");
    }
  };

  if (state === "ready") return <section className="verification-ticket" aria-labelledby="verification-code-heading"><ShieldCheck /><div><p className="eyebrow">Valid for 24 hours</p><h2 id="verification-code-heading">Show this code at a participating shelter</h2><code>{code}</code><p>The employee will inspect your physical ID and enter or scan its barcode. This code contains no identity or care-history data.</p></div><button className="button secondary" type="button" onClick={() => void navigator.clipboard.writeText(code)}><Clipboard size={17} /> Copy code</button></section>;

  return <div className="notice"><div><strong>Verify in person at a shelter</strong><p>Generate a private request code, then show your physical ID to an authorized shelter employee. Fido stores reconciliation signals—not an image of your ID.</p></div><button className="button primary" disabled={state === "loading"} onClick={() => void begin()}>{state === "loading" ? "Preparing…" : "Get verification code"}</button>{state === "error" && <p className="form-error" role="alert">{message}</p>}</div>;
}
