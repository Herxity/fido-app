import { ClipboardList, HeartHandshake, LogOut, PawPrint, QrCode, ShieldCheck, UserRound } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { useSession } from "../auth/AuthContext";
import { api } from "../api/client";
import { ErrorState, LoadingState } from "./States";

const ownerLinks = [{ to: "/owner/history", label: "Care history", icon: HeartHandshake }, { to: "/owner/pass", label: "Share history", icon: QrCode }, { to: "/owner/account", label: "Account", icon: UserRound }];
const shelterLinks = [{ to: "/shelter/queue", label: "Active records", icon: ClipboardList }, { to: "/shelter/pets", label: "Pet registry", icon: PawPrint }, { to: "/shelter/lookup", label: "Owner lookup", icon: QrCode }, { to: "/shelter/disputes", label: "Disputes", icon: ShieldCheck }];

export function AppShell() {
  const { name, signOut } = useSession();
  const location = useLocation();
  const requestedMode = location.pathname.startsWith("/shelter") ? "shelter" : "owner";
  const demo = import.meta.env.VITE_USE_DEMO_DATA === "true";
  const viewer = useQuery({ queryKey: ["me", demo ? requestedMode : "current"], queryFn: () => api.getMe(requestedMode) });
  if (viewer.isLoading) return <LoadingState label="Opening your workspace…" />;
  if (viewer.isError || !viewer.data) return <ErrorState retry={() => void viewer.refetch()} />;
  if (!demo && requestedMode !== viewer.data.mode) return <Navigate to={viewer.data.mode === "shelter" ? "/shelter/queue" : "/owner/history"} replace />;
  const shelter = viewer.data.mode === "shelter";
  const links = shelter ? shelterLinks : ownerLinks;
  return <div className="app-shell">
    <header className="topbar"><NavLink className="wordmark" to={shelter ? "/shelter/queue" : "/owner/history"}><span className="tag-mark">F</span><span>Fido</span></NavLink><div className="context"><span className="mode-label">{shelter ? viewer.data.shelter?.name : "My records"}</span><span>{viewer.data.name || name}</span><button className="icon-button" onClick={() => void signOut()} aria-label="Sign out"><LogOut size={18} /></button></div></header>
    <nav className="primary-nav" aria-label="Primary navigation">{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to}><Icon size={18} /><span>{label}</span></NavLink>)}</nav>
    <main className="workspace" id="main"><Outlet context={{ viewer: viewer.data }} /></main>
    {demo && <footer className="mode-switch">Demo views: <NavLink to={shelter ? "/owner/history" : "/shelter/queue"}>Switch to {shelter ? "owner" : "shelter"} view</NavLink></footer>}
  </div>;
}
