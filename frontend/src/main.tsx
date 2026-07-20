import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthGate, AuthProvider } from "./auth/AuthContext";
import "./styles.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000, gcTime: 5 * 60_000, refetchOnWindowFocus: false }, mutations: { retry: 0 } } });

createRoot(document.getElementById("root")!).render(<StrictMode><QueryClientProvider client={queryClient}><AuthProvider><AuthGate><BrowserRouter><a className="skip-link" href="#main">Skip to main content</a><App /></BrowserRouter></AuthGate></AuthProvider></QueryClientProvider></StrictMode>);
