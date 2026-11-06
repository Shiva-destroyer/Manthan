export type Page = "home" | "lab" | "run" | "results" | "judge" | "system";

const PAGES: readonly Page[] = ["home", "lab", "run", "results", "judge", "system"];

export function parseHash(hash: string): { page: Page; params: URLSearchParams } {
  const [path = "", query = ""] = hash.replace(/^#\/?/, "").split("?");
  const page = PAGES.find((p) => p === path) ?? "home";
  return { page, params: new URLSearchParams(query) };
}

export function hrefFor(page: Page, params: Record<string, string>): string {
  const qs = new URLSearchParams(params).toString();
  return `#/${page}${qs ? `?${qs}` : ""}`;
}

// replaceState does not fire hashchange, so a replace sends it by hand.
export function navigate(href: string, replace = false): void {
  if (replace) {
    history.replaceState(null, "", href);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  } else {
    window.location.hash = href;
  }
}
