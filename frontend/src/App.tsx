import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { NewDispute } from "./pages/owner/NewDispute";
import { OwnerAccount } from "./pages/owner/OwnerAccount";
import { OwnerHistory } from "./pages/owner/OwnerHistory";
import { OwnerPass } from "./pages/owner/OwnerPass";
import { OwnerLookup } from "./pages/shelter/OwnerLookup";
import { PetDetail, RegistryWelcome } from "./pages/shelter/PetDetail";
import { PetRegistry } from "./pages/shelter/PetRegistry";
import { ShelterDisputes } from "./pages/shelter/ShelterDisputes";
import { ShelterQueue } from "./pages/shelter/ShelterQueue";

export default function App() {
  return <Routes><Route element={<AppShell />}>
    <Route index element={<Navigate to="/owner/history" replace />} />
    <Route path="owner/history" element={<OwnerHistory />} />
    <Route path="owner/pass" element={<OwnerPass />} />
    <Route path="owner/account" element={<OwnerAccount />} />
    <Route path="owner/disputes/new" element={<NewDispute />} />
    <Route path="shelter/queue" element={<ShelterQueue />} />
    <Route path="shelter/pets" element={<PetRegistry />}><Route index element={<RegistryWelcome />} /><Route path=":petId" element={<PetDetail />} /></Route>
    <Route path="shelter/lookup" element={<OwnerLookup />} />
    <Route path="shelter/disputes" element={<ShelterDisputes />} />
    <Route path="*" element={<Navigate to="/owner/history" replace />} />
  </Route></Routes>;
}
