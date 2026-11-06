import { TOUR_STEPS } from "../lib/tour.ts";

export function Tour({ step, onNext, onSkip }: { step: number; onNext(): void; onSkip(): void }) {
  const last = step === TOUR_STEPS.length - 1;
  return (
    <div className="tour" role="dialog" aria-label="Guided tour" onKeyDown={(e) => e.key === "Escape" && onSkip()}>
      <p className="muted">Step {step + 1} of {TOUR_STEPS.length}</p>
      <p>{TOUR_STEPS[step]!.text}</p>
      <div className="tour-buttons">
        <button type="button" onClick={onSkip}>Skip tour</button>
        <button type="button" autoFocus onClick={onNext}>{last ? "Done" : "Next"}</button>
      </div>
    </div>
  );
}
