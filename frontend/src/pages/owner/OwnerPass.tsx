import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { Clock3, FlaskConical, LockKeyhole } from "lucide-react";
import { api } from "../../api/client";
import { ErrorState } from "../../components/States";

export function OwnerPass() {
  const token = useMutation({ mutationFn: api.createLookupToken });
  const [now, setNow] = useState(Date.now());
  const localTesting = import.meta.env.DEV && import.meta.env.VITE_DEPLOYMENT_STAGE !== "production";
  useEffect(() => { if (!token.data) return; const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, [token.data]);
  useEffect(() => {
    if (!localTesting || !token.data) return;
    window.sessionStorage.setItem("fido:local-owner-pass", JSON.stringify(token.data));
  }, [localTesting, token.data]);
  const seconds = token.data ? Math.max(0, Math.ceil((new Date(token.data.expiresAt).getTime() - now) / 1000)) : 0;
  const expired = token.data && seconds === 0;
  return <div className="page-stack narrow">
    <header className="page-header"><div><p className="eyebrow">Owner-authorized access</p><h1>Share your care history</h1><p>Generate this pass while you are with shelter staff. It works once and reveals no personal information on its own.</p></div></header>
    {token.isError ? <ErrorState retry={() => token.mutate()} /> : <section className="pass-panel">
      {!token.data || expired ? <><div className="pass-illustration"><LockKeyhole size={36} /></div><h2>{expired ? "That pass has expired" : "Ready when you are"}</h2><p>A new pass is valid for five minutes. Only the shelter that scans it can use the resulting session.</p><button className="button primary large" onClick={() => token.mutate()} disabled={token.isPending}>{token.isPending ? "Creating secure pass…" : expired ? "Create a new pass" : "Create shelter pass"}</button></> : <><div className="qr-frame" aria-label="QR code containing a one-time shelter lookup token"><QRCodeSVG value={token.data.token} size={224} bgColor="#fffdf8" fgColor="#172b3a" level="M" /></div><h2>Show this to shelter staff</h2><p className="countdown"><Clock3 size={18} /> Expires in <strong>{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}</strong></p>{localTesting && <div className="local-test-note" role="status"><FlaskConical size={17} /><span>Local test pass saved. Switch to a shelter account in this tab, then choose <strong>Use latest local pass</strong>.</span></div>}<p className="privacy-note">The code is single-use. It contains an opaque pass, not your name or history.</p></>}
    </section>}
  </div>;
}
