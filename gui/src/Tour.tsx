import { ErrorBoundary } from "./ErrorBoundary";
import { useEffect, useState } from "react";
import { ActionButton } from "./ActionButton";

const steps = [
  { page: "Home", selector: '[aria-label="Home"] .primary', sentence: "Add videos here, then choose Standard cleanup or Fast motion and resizing." },
  { page: "Schedule", selector: '[aria-label="Schedule"] .page-heading label', sentence: "Choose the hours when VideoEnhancer can work." },
  { page: "History", selector: '[aria-label="History"] .page-heading', sentence: "Open finished videos in History to play them or compare models again." },
  { page: "Models", selector: '.model-grid', sentence: "Install verified models here and choose your defaults in their details." },
  { page: "Settings", selector: '.settings-page .page-heading', sentence: "Change appearance, output defaults and speed calibration in Settings." },
];
function TourContent({ navigate, close }: { navigate(page: string): void; close(): void }) {
  const [step, setStep] = useState(0);
  const [box, setBox] = useState<DOMRect>();
  useEffect(() => {
    navigate(steps[step].page);
    const timer = setTimeout(() => setBox(document.querySelector(steps[step].selector)?.getBoundingClientRect()), 100);
    return () => clearTimeout(timer);
  }, [step, navigate]);
  return <div className="tour-layer">
    {box && <div className="tour-highlight" aria-hidden="true" style={{ left: box.left - 5, top: box.top - 5, width: box.width + 10, height: box.height + 10 }} />}
    <div className="tour-card" role="dialog" aria-label="Welcome tour"><p>{steps[step].sentence}</p><span>{step + 1} / {steps.length}</span>
      <div className="actions"><ActionButton onClick={close}>Skip</ActionButton><ActionButton className="primary" onClick={() => step === steps.length - 1 ? close() : setStep(step + 1)}>{step === steps.length - 1 ? "Done" : "Next"}</ActionButton></div>
    </div>
  </div>;
}

export function Tour(props: Parameters<typeof TourContent>[0]) {
  return <ErrorBoundary scope="Tutorial"><TourContent {...props} /></ErrorBoundary>;
}
