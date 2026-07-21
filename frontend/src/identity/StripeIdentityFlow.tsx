import { loadStripe } from "@stripe/stripe-js";
import { useState } from "react";
import { api } from "../api/client";

export function StripeIdentityFlow({ onComplete }: { onComplete: () => void }) {
  const [state, setState] = useState<"idle" | "loading" | "submitted" | "error">("idle");
  const [message, setMessage] = useState("");

  const begin = async () => {
    setState("loading");
    setMessage("");
    try {
      const publishableKey = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY;
      if (!publishableKey) throw new Error("Stripe Identity is not configured.");
      const stripe = await loadStripe(publishableKey);
      if (!stripe) throw new Error("Stripe Identity could not load.");
      const inquiry = await api.createInquiry();
      if (!inquiry.clientSecret) throw new Error("Verification is already processing.");
      const result = await stripe.verifyIdentity(inquiry.clientSecret);
      if (result.error) throw new Error(result.error.message);
      setState("submitted");
      onComplete();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Verification could not open.");
      setState("error");
    }
  };

  return <div className="notice"><div><strong>Verify once, carry your history forward</strong><p>Stripe checks your government ID and live selfie. Fido stores the verification decision and privacy-preserving match signals—not your ID images.</p>{state === "submitted" && <p className="status-note" role="status">Submitted securely. We’ll update this record when verification finishes.</p>}</div><button className="button primary" disabled={state === "loading" || state === "submitted"} onClick={begin}>{state === "loading" ? "Preparing…" : state === "submitted" ? "Verification submitted" : "Verify identity"}</button>{state === "error" && <p className="form-error" role="alert">{message} Try again shortly.</p>}</div>;
}
