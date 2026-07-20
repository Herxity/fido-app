import { render, screen } from "@testing-library/react";
import { demoHistory } from "../api/demo";
import { CareTimeline } from "./CareTimeline";

test("presents factual entries, source shelters, corrections, and disputes", () => {
  render(<CareTimeline entries={demoHistory} />);
  expect(screen.getByRole("list", { name: "Care journey" })).toBeInTheDocument();
  expect(screen.getByText("Returned to shelter · June")).toBeInTheDocument();
  expect(screen.getAllByText("Meadow Lane Rescue")).toHaveLength(2);
  expect(screen.getByText("Corrects an earlier entry")).toBeInTheDocument();
  expect(screen.getByText(/Dispute open/)).toBeInTheDocument();
  expect(screen.queryByText(/score/i)).not.toBeInTheDocument();
});
