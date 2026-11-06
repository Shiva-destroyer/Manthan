"""Cross-domain OWASP×ATLAS coverage heatmap (PRD §8.6, FR-C8).

Aggregates finding counts across prompt / agent / RAG into one matrix (OWASP
rows × ATLAS cols) and renders it to an inline SVG so the HTML report stays
self-contained. Matplotlib runs head-less (Agg); no display, no network.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable


def _svg_body(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    svg = buf.getvalue()
    # Strip the XML declaration / doctype so it inlines cleanly into HTML.
    match = re.search(r"<svg.*?</svg>", svg, re.DOTALL)
    return match.group(0) if match else svg


def render_heatmap(
    counts: dict[tuple[str, str], int],
    owasp_order: Iterable[str] | None = None,
    atlas_order: Iterable[str] | None = None,
    title: str = "OWASP × ATLAS coverage (findings across prompt · agent · RAG)",
) -> str:
    """Return an inline ``<svg>`` string for the coverage heatmap."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    owasp_ids = sorted({o for (o, _a) in counts} | set(owasp_order or []))
    atlas_ids = sorted({a for (_o, a) in counts} | set(atlas_order or []))
    if not owasp_ids or not atlas_ids:
        # Nothing to show yet — emit a tiny placeholder SVG.
        fig = plt.figure(figsize=(4, 1))
        fig.text(0.5, 0.5, "no findings yet", ha="center", va="center")
        out = _svg_body(fig)
        plt.close(fig)
        return out

    mat = np.zeros((len(owasp_ids), len(atlas_ids)), dtype=int)
    for (o, a), n in counts.items():
        if o in owasp_ids and a in atlas_ids:
            mat[owasp_ids.index(o), atlas_ids.index(a)] = n

    fig, ax = plt.subplots(
        figsize=(max(6, 0.7 * len(atlas_ids) + 3), max(3, 0.55 * len(owasp_ids) + 2))
    )
    im = ax.imshow(mat, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(atlas_ids)))
    ax.set_xticklabels(atlas_ids, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(owasp_ids)))
    ax.set_yticklabels(owasp_ids, fontsize=9)
    ax.set_title(title, fontsize=10)
    for i in range(len(owasp_ids)):
        for j in range(len(atlas_ids)):
            v = mat[i, j]
            if v:
                ax.text(
                    j,
                    i,
                    str(v),
                    ha="center",
                    va="center",
                    color="black" if v < mat.max() * 0.6 else "white",
                    fontsize=8,
                )
    fig.colorbar(im, ax=ax, shrink=0.8, label="findings")
    out = _svg_body(fig)
    plt.close(fig)
    return out
