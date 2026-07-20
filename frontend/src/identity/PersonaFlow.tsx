import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

declare global {
  interface Window { Persona?: new (options: Record<string, unknown>) => { open: () => void; destroy: () => void }; }
}

const SCRIPT = "https://cdn.withpersona.com/dist/persona-v5.1.2.js";

export function PersonaFlow({ onComplete }: { onComplete: () => void }) {
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const client = useRef<{ destroy: () => void } | null>(null);
  useEffect(() => () => client.current?.destroy(), []);

  const begin = async () => {
    setState("loading");
    try {
      const inquiry = await api.createInquiry();
      if (!window.Persona) await new Promise<void>((resolve, reject) => {
        const script = document.createElement("script"); script.src = SCRIPT; script.async = true; script.onload = () => resolve(); script.onerror = () => reject(new Error("Persona failed to load")); document.head.append(script);
      });
      const instance = new window.Persona!({ inquiryId: inquiry.inquiryId, sessionToken: inquiry.sessionToken, onComplete: () => { setState("idle"); onComplete(); }, onCancel: () => setState("idle"), onError: () => setState("error") });
      client.current = instance; instance.open();
    } catch { setState("error"); }
  };

  return <div className="notice"><div><strong>Verify once, carry your history forward</strong><p>Persona checks your ID and live selfie. Fido never receives your ID images.</p></div><button className="button primary" disabled={state === "loading"} onClick={begin}>{state === "loading" ? "Preparing…" : "Verify identity"}</button>{state === "error" && <p className="form-error" role="alert">Verification could not open. Try again shortly.</p>}</div>;
}
