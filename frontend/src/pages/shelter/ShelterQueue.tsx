import { ArrowRight, ClipboardCheck, QrCode, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { StatusPill } from "../../components/States";

const tasks = [
  { kind: "Intake", title: "Complete Miso’s intake record", meta: "HC-2418 · arrived 24 minutes ago", to: "/shelter/pets/pet-1", tone: "attention" as const },
  { kind: "Review", title: "Owner correction request", meta: "June · response due in 2 days", to: "/shelter/disputes", tone: "attention" as const },
  { kind: "Handoff", title: "Confirm Otis foster placement", meta: "HC-2417 · foster starts today", to: "/shelter/pets/pet-2", tone: "neutral" as const }
];

export function ShelterQueue() { return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">Monday, July 20</p><h1>Active records</h1><p>Three handoffs need attention at the intake desk.</p></div><Link className="button primary" to="/shelter/lookup"><QrCode size={17} /> Scan owner pass</Link></header>
  <section className="queue" aria-labelledby="queue-title"><div className="section-heading"><div><p className="eyebrow">Work queue</p><h2 id="queue-title">Continue where the team left off</h2></div></div>{tasks.map((task) => <Link className="queue-row" to={task.to} key={task.title}><span className="queue-icon">{task.kind === "Review" ? <ShieldAlert /> : <ClipboardCheck />}</span><span><StatusPill tone={task.tone}>{task.kind}</StatusPill><strong>{task.title}</strong><small>{task.meta}</small></span><ArrowRight size={20} /></Link>)}</section>
  <aside className="desk-note"><strong>Desk handoff</strong><p>Owner lookups require a pass generated in the owner’s presence. Never ask for a screenshot of an identity document.</p></aside></div>; }
