import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { NavLink, Outlet, useOutletContext } from "react-router-dom";
import { api } from "../../api/client";
import type { Viewer } from "../../api/types";
import { EmptyState, ErrorState, LoadingState, StatusPill } from "../../components/States";
import { PetForm, type PetFormData } from "./PetForm";

export function PetRegistry() {
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const queryClient = useQueryClient();
  const { viewer } = useOutletContext<{ viewer: Viewer }>();
  const shelterId = viewer.shelter?.id;
  const pets = useQuery({ queryKey: ["pets", shelterId], queryFn: () => api.getPets(shelterId!), enabled: Boolean(shelterId) });
  const createPet = useMutation({ mutationFn: (data: PetFormData) => api.createPet(shelterId!, data), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["pets", shelterId] }); setCreating(false); } });
  const filtered = useMemo(() => pets.data?.items.filter((pet) => `${pet.name} ${pet.recordNumber} ${pet.breedDescription}`.toLowerCase().includes(search.toLowerCase())) ?? [], [pets.data, search]);
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">Shelter ledger</p><h1>Pet registry</h1><p>Find a kennel card by name, record number, or breed description.</p></div><button className="button primary" onClick={() => setCreating(true)}>Add intake record</button></header>
    {creating && <section className="form-panel" aria-labelledby="new-pet-title"><div className="section-heading"><div><p className="eyebrow">New shelter record</p><h2 id="new-pet-title">Pet intake</h2></div></div><PetForm submitLabel="Create intake record" pending={createPet.isPending} serverError={createPet.isError} onSubmit={(data) => createPet.mutate(data)} onCancel={() => setCreating(false)} /></section>}
    <div className="registry-layout"><section className="registry-list" aria-label="Pet registry"><label className="search-control"><Search size={18} /><span className="sr-only">Search registry</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search records" /></label>
      {!shelterId ? <ErrorState /> : pets.isLoading ? <LoadingState /> : pets.isError ? <ErrorState retry={() => void pets.refetch()} /> : !filtered.length ? <EmptyState title="No matching records">Try a pet name or shelter record number.</EmptyState> : <ul>{filtered.map((pet) => <li key={pet.id}><NavLink to={`/shelter/pets/${pet.id}`}><span className="pet-monogram">{pet.name[0]}</span><span><strong>{pet.name}</strong><small>{pet.recordNumber} · {pet.breedDescription}</small></span><StatusPill tone={pet.lifecycleState === "available" ? "positive" : "neutral"}>{pet.lifecycleState}</StatusPill></NavLink></li>)}</ul>}
    </section><section className="registry-detail"><Outlet context={{ shelterId }} /></section></div>
  </div>;
}
