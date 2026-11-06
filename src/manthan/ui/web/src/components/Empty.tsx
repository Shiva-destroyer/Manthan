import type { ReactNode } from "react";

export function Empty({ what, how }: { what: string; how: ReactNode }) {
  return (
    <div className="empty">
      <p>{what}</p>
      <p>{how}</p>
    </div>
  );
}
