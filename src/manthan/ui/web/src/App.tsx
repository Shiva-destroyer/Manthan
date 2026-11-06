import { useEffect, useRef, useState } from "react";
import { type Page, hrefFor, parseHash } from "./lib/route.ts";
import { HomePage } from "./pages/Home.tsx";
import { LabPage } from "./pages/Lab.tsx";
import { RunPage } from "./pages/Run.tsx";
import { JudgePage } from "./pages/Judge.tsx";
import { SystemPage } from "./pages/System.tsx";
import { ResultsPage } from "./pages/Results.tsx";
import logo from "./assets/logo.svg";

const NAV: { page: Page; label: string }[] = [
  { page: "home", label: "Home" },
  { page: "lab", label: "Virtual Lab" },
  { page: "run", label: "Run" },
  { page: "results", label: "Results" },
  { page: "judge", label: "Judge" },
  { page: "system", label: "System" },
];

function useHash(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}

export function App() {
  const { page, params } = parseHash(useHash());
  const first = useRef(true);
  useEffect(() => {
    document.title = `${NAV.find((n) => n.page === page)?.label ?? "Manthan"} - Manthan`;
    if (first.current) first.current = false;
    else {
      const h = document.querySelector<HTMLElement>("main h1");
      h?.setAttribute("tabindex", "-1");
      h?.focus();
    }
  }, [page]);
  return (
    <>
      <header className="bar">
        <div className="bar-inner">
          <a className="wordmark" href={hrefFor("home", {})}>
            <img src={logo} alt="" width={48} height={48} />
            Manthan
          </a>
          <nav aria-label="Pages">
            {NAV.map((n) => (
              <a
                key={n.page}
                className="nav-link"
                href={hrefFor(n.page, {})}
                aria-current={n.page === page ? "page" : undefined}
              >
                {n.label}
              </a>
            ))}
          </nav>
        </div>
      </header>
      <main className="frame">
        {page === "home" ? (
          <HomePage />
        ) : page === "lab" ? (
          <LabPage params={params} />
        ) : page === "run" ? (
          <RunPage params={params} />
        ) : page === "results" ? (
          <ResultsPage params={params} />
        ) : page === "judge" ? (
          <JudgePage params={params} />
        ) : (
          <SystemPage />
        )}
      </main>
    </>
  );
}
