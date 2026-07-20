import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { ErrorState, LoadingState, StatusPill } from "../../components/States";
import { PetForm, type PetFormData } from "./PetForm";

export function PetDetail() {
  const { petId = "" } = useParams();
  const { shelterId } = useOutletContext<{ shelterId?: string }>();
  const [mode, setMode] = useState<"view" | "edit">("view");
  const queryClient = useQueryClient();
  const pet = useQuery({ queryKey: ["pet", shelterId, petId], queryFn: () => api.getPet(shelterId!, petId), enabled: Boolean(petId && shelterId) });
  const updatePet = useMutation({ mutationFn: (data: PetFormData) => api.updatePet(shelterId!, petId, data), onSuccess: async () => { await Promise.all([queryClient.invalidateQueries({ queryKey: ["pet", shelterId, petId] }), queryClient.invalidateQueries({ queryKey: ["pets", shelterId] })]); setMode("view"); } });
  if (pet.isLoading) return <LoadingState label="Opening kennel card…" />;
  if (pet.isError || !pet.data) return <ErrorState retry={() => void pet.refetch()} />;
  const p = pet.data;
  if (mode === "edit") return <article className="kennel-card"><header><div><p className="eyebrow">Edit kennel card</p><h2>{p.name}</h2></div></header><PetForm initial={p} submitLabel="Save pet details" pending={updatePet.isPending} serverError={updatePet.isError} onSubmit={(data) => updatePet.mutate(data)} onCancel={() => setMode("view")} /></article>;
  return <article className="kennel-card"><header><div><p className="eyebrow">Kennel card · {p.recordNumber}</p><h2>{p.name}</h2><p>{p.breedDescription}</p></div><StatusPill tone={p.lifecycleState === "available" ? "positive" : "neutral"}>{p.lifecycleState}</StatusPill></header><dl><div><dt>Species</dt><dd>{p.species}</dd></div><div><dt>Sex</dt><dd>{p.sex}</dd></div><div><dt>Color</dt><dd>{p.color || "Not recorded"}</dd></div><div><dt>Birth date</dt><dd>{p.approximateBirthDate ? `Approx. ${p.approximateBirthDate}` : "Not recorded"}</dd></div><div><dt>Altered</dt><dd>{p.altered ? "Yes" : "Not recorded"}</dd></div></dl><div className="card-actions"><button className="button secondary" onClick={() => setMode("edit")}>Edit pet details</button></div><p className="privacy-note">To record an owner handoff, redeem the owner’s active shelter pass first.</p></article>;
}

export function RegistryWelcome() { return <div className="detail-placeholder"><span className="tag-mark">F</span><strong>Select a shelter record</strong><p>The full kennel card will open here without losing your place in the registry.</p></div>; }
