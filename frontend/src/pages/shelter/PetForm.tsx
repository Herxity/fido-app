import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { PetSummary } from "../../api/types";

const petSchema = z.object({
  recordNumber: z.string().trim().min(2, "Enter the shelter record number.").max(60),
  name: z.string().trim().min(1, "Enter the pet’s name.").max(100),
  species: z.string().trim().min(2, "Enter the species.").max(80),
  breedDescription: z.string().trim().min(2, "Enter a breed description.").max(160),
  sex: z.string().trim().min(1, "Enter the recorded sex.").max(40),
  approximateBirthDate: z.string().optional(),
  color: z.string().trim().max(100).optional(),
  altered: z.boolean(),
  lifecycleState: z.enum(["available", "adopted", "foster", "transferred", "inactive"])
});
export type PetFormData = z.infer<typeof petSchema>;

export function PetForm({ initial, submitLabel, pending, serverError, onSubmit, onCancel }: { initial?: PetSummary; submitLabel: string; pending?: boolean; serverError?: boolean; onSubmit: (data: PetFormData) => void; onCancel: () => void }) {
  const { register, handleSubmit, formState: { errors } } = useForm<PetFormData>({
    resolver: zodResolver(petSchema),
    defaultValues: initial ? { recordNumber: initial.recordNumber, name: initial.name, species: initial.species, breedDescription: initial.breedDescription, sex: initial.sex, approximateBirthDate: initial.approximateBirthDate || "", color: initial.color || "", altered: initial.altered || false, lifecycleState: initial.lifecycleState } : { altered: false, lifecycleState: "available" }
  });
  return <form className="record-form" onSubmit={handleSubmit(onSubmit)} noValidate>
    <div className="field-grid"><div><label htmlFor="pet-record">Record number</label><input id="pet-record" {...register("recordNumber")} />{errors.recordNumber && <p className="form-error">{errors.recordNumber.message}</p>}</div><div><label htmlFor="pet-name">Pet name</label><input id="pet-name" {...register("name")} />{errors.name && <p className="form-error">{errors.name.message}</p>}</div><div><label htmlFor="pet-species">Species</label><input id="pet-species" {...register("species")} />{errors.species && <p className="form-error">{errors.species.message}</p>}</div><div><label htmlFor="pet-breed">Breed description</label><input id="pet-breed" {...register("breedDescription")} />{errors.breedDescription && <p className="form-error">{errors.breedDescription.message}</p>}</div><div><label htmlFor="pet-sex">Recorded sex</label><input id="pet-sex" {...register("sex")} />{errors.sex && <p className="form-error">{errors.sex.message}</p>}</div><div><label htmlFor="pet-birth">Approximate birth date</label><input id="pet-birth" type="date" {...register("approximateBirthDate")} /></div><div><label htmlFor="pet-color">Color</label><input id="pet-color" {...register("color")} /></div><div><label htmlFor="pet-state">Lifecycle state</label><select id="pet-state" {...register("lifecycleState")}><option value="available">Available</option><option value="foster">Foster</option><option value="adopted">Adopted</option><option value="transferred">Transferred</option><option value="inactive">Inactive</option></select></div></div>
    <label className="check-control"><input type="checkbox" {...register("altered")} /> Spayed or neutered</label>
    {serverError && <p className="form-error" role="alert">The record could not be saved. Check the details and try again.</p>}
    <div className="form-actions"><button type="button" className="button secondary" onClick={onCancel}>Cancel</button><button className="button primary" disabled={pending}>{pending ? "Saving…" : submitLabel}</button></div>
  </form>;
}
