import type { ReactNode } from "react";

export function LoadingState({ label = "Loading records…" }: { label?: string }) { return <div className="state" role="status"><span className="spinner" />{label}</div>; }
export function ErrorState({ retry }: { retry?: () => void }) { return <div className="state error-state" role="alert"><strong>That record could not be reached.</strong><span>Your work is safe. Check the connection and try again.</span>{retry && <button className="button secondary" onClick={retry}>Try again</button>}</div>; }
export function EmptyState({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) { return <div className="state empty-state"><span className="tag-mark" aria-hidden="true">F</span><strong>{title}</strong><span>{children}</span>{action}</div>; }
export function StatusPill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "positive" | "attention" }) { return <span className={`status ${tone}`}>{children}</span>; }
