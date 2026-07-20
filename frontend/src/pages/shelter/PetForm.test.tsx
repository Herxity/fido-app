import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { PetForm } from "./PetForm";

test("validates and submits a new shelter pet record", async () => {
  const user = userEvent.setup();
  const submit = vi.fn();
  render(<PetForm submitLabel="Create intake record" onSubmit={submit} onCancel={() => undefined} />);
  await user.type(screen.getByLabelText("Record number"), "HC-2501");
  await user.type(screen.getByLabelText("Pet name"), "Pip");
  await user.type(screen.getByLabelText("Species"), "Cat");
  await user.type(screen.getByLabelText("Breed description"), "Domestic shorthair");
  await user.type(screen.getByLabelText("Recorded sex"), "Female");
  await user.type(screen.getByLabelText("Color"), "Gray");
  await user.click(screen.getByRole("checkbox", { name: "Spayed or neutered" }));
  await user.click(screen.getByRole("button", { name: "Create intake record" }));
  expect(submit).toHaveBeenCalledOnce();
  expect(submit.mock.calls[0][0]).toEqual(expect.objectContaining({ recordNumber: "HC-2501", name: "Pip", species: "Cat", altered: true, lifecycleState: "available" }));
});
