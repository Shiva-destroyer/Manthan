"""Shared reporter: Jinja2 HTML/MD + cross-domain OWASP×ATLAS heatmap."""

from manthan.core.report.heatmap import render_heatmap
from manthan.core.report.report import Reporter, ReportPaths

__all__ = ["Reporter", "ReportPaths", "render_heatmap"]
