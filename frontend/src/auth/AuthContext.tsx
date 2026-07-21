import { ClerkProvider, SignInButton, SignUpButton, useAuth, useUser } from "@clerk/react";
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { configureApiAuth, configureApiUnauthorized } from "../api/client";

interface Session { ready: boolean; signedIn: boolean; name: string; provider: "clerk" | "demo"; getToken: () => Promise<string | null>; signOut: () => Promise<void>; }
const SessionContext = createContext<Session | null>(null);
export const useSession = () => {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
};

function ApiAuthBridge({ children, session }: { children: ReactNode; session: Session }) {
  useEffect(() => configureApiAuth(session.getToken), [session.getToken]);
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

function ClerkSession({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken, signOut } = useAuth();
  const { user } = useUser();
  const queryClient = useQueryClient();
  useEffect(() => {
    configureApiUnauthorized(() => queryClient.clear());
    if (isLoaded && !isSignedIn) queryClient.clear();
    return () => configureApiUnauthorized(() => undefined);
  }, [isLoaded, isSignedIn, queryClient]);
  const secureSignOut = async () => { queryClient.clear(); await signOut(); };
  return <ApiAuthBridge session={{ ready: isLoaded, signedIn: Boolean(isSignedIn), name: user?.fullName || user?.primaryEmailAddress?.emailAddress || "Account", provider: "clerk", getToken, signOut: secureSignOut }}>{children}</ApiAuthBridge>;
}

function DemoSession({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const session: Session = { ready: true, signedIn: true, name: "Demo account", provider: "demo", getToken: async () => null, signOut: async () => { queryClient.clear(); } };
  return <ApiAuthBridge session={session}>{children}</ApiAuthBridge>;
}

export function ConfigurationError({ reason }: { reason: string }) {
  return <main className="full-state config-error" role="alert"><span className="tag-mark">F</span><h1>Fido is not configured</h1><p>{reason}</p><p>Contact the deployment administrator. Access remains closed until configuration is corrected.</p></main>;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const key = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
  const demo = import.meta.env.VITE_USE_DEMO_DATA === "true";
  const syntheticStaging = import.meta.env.VITE_DEPLOYMENT_STAGE === "staging" && import.meta.env.VITE_DEMO_SANDBOX_ACKNOWLEDGED === "true";
  if (import.meta.env.PROD && demo && !syntheticStaging) return <ConfigurationError reason="Demo mode requires an explicitly acknowledged synthetic staging build." />;
  if (demo) return <DemoSession>{children}</DemoSession>;
  if (!key) return <ConfigurationError reason="A Clerk publishable key is required." />;
  return <ClerkProvider publishableKey={key}><ClerkSession>{children}</ClerkSession></ClerkProvider>;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const session = useSession();
  if (!session.ready) return <div className="full-state" role="status"><span className="spinner" />Checking your session…</div>;
  if (!session.signedIn) return <main className="sign-in"><div><p className="eyebrow">Fido records</p><h1>Your care history starts here.</h1><p>Sign in to review an existing care record, or create an account to begin a verified adoption history.</p><div className="auth-actions"><SignInButton mode="modal"><button className="button primary large">Sign in</button></SignInButton><SignUpButton mode="modal"><button className="button secondary large">Create account</button></SignUpButton></div></div><aside className="auth-note"><span className="tag-mark">F</span><div><strong>A record built around care.</strong><p>Your identity and care history remain protected until you authenticate.</p></div></aside></main>;
  return children;
}
