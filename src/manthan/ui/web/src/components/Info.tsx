import { useId, useState } from "react";
import { lookup } from "../lib/glossary.ts";

export function Info({ name }: { name: string }) {
  const [open, setOpen] = useState(false);
  const panel = useId();
  const entry = lookup(name);
  if (!entry) return null;
  return (
    <>
      <button
        type="button"
        className="info"
        aria-expanded={open}
        aria-controls={panel}
        aria-label={`What is ${entry.term}?`}
        onClick={() => setOpen(!open)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
      >
        (i)
      </button>
      <span id={panel} className="info-panel" hidden={!open}>
        <span>{entry.plain}</span>
        <code>{entry.technical}</code>
      </span>
    </>
  );
}
