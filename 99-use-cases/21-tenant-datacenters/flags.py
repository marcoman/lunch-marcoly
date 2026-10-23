"""Flag keys, size-class colors, and the segment list for the datacenter lab.

The border flag is one string for the whole floor. The fill flag is one
boolean. Size class picks the hue inside a palette, so every Small matches.

Feature flags — multivariate variations
https://launchdarkly.com/docs/home/flags/variations

Feature flags — boolean variations
https://launchdarkly.com/docs/home/flags/boolean

Segments — https://launchdarkly.com/docs/home/flags/segments
"""

from __future__ import annotations

from typing import Any

FLAG_BORDER = "tenant-border-palette"
FLAG_FILL = "tenant-box-fill"

# Four hues per palette, one per size class. Yellow and orange are left out
# of ROYGBIV so a tinted fill does not wash out the light tenant name.
PALETTES: dict[str, dict[str, str]] = {
    "roygbiv": {
        "small": "#3b82f6",
        "medium": "#22c55e",
        "large": "#ef4444",
        "unknown": "#a78bfa",
    },
    "grays": {
        "small": "#d4d4d8",
        "medium": "#a1a1aa",
        "large": "#f4f4f5",
        "unknown": "#71717a",
    },
    "earth": {
        "small": "#84cc16",
        "medium": "#d97706",
        "large": "#ea580c",
        "unknown": "#a8a29e",
    },
    "ocean": {
        "small": "#22d3ee",
        "medium": "#14b8a6",
        "large": "#38bdf8",
        "unknown": "#99f6e4",
    },
}

# Attribute rules. An all-five tenant also matches multi-site.
SEGMENTS: list[dict[str, Any]] = [
    {"key": "tenant-size-small", "name": "Small tenants", "attribute": "sizeClass", "values": ["small"]},
    {"key": "tenant-size-medium", "name": "Medium tenants", "attribute": "sizeClass", "values": ["medium"]},
    {"key": "tenant-size-large", "name": "Large tenants", "attribute": "sizeClass", "values": ["large"]},
    {"key": "tenant-size-unknown", "name": "Unknown tenants", "attribute": "sizeClass", "values": ["unknown"]},
    {"key": "tenant-dc-01", "name": "DC01", "attribute": "datacenter", "values": ["DC01"]},
    {"key": "tenant-dc-02", "name": "DC02", "attribute": "datacenter", "values": ["DC02"]},
    {"key": "tenant-dc-03", "name": "DC03", "attribute": "datacenter", "values": ["DC03"]},
    {"key": "tenant-dc-04", "name": "DC04", "attribute": "datacenter", "values": ["DC04"]},
    {"key": "tenant-dc-05", "name": "DC05", "attribute": "datacenter", "values": ["DC05"]},
    {"key": "tenant-footprint-single", "name": "Single-site tenants", "attribute": "span", "values": [1]},
    {"key": "tenant-footprint-multi", "name": "Multi-site tenants", "attribute": "span", "values": [2, 3, 5]},
    {"key": "tenant-footprint-all-five", "name": "Tenants in all five datacenters", "attribute": "span", "values": [5]},
]


def hue(palette: str, size_class: str) -> str | None:
    """Color for this size class, or None when the palette is none."""
    return PALETTES.get(str(palette), {}).get(size_class)
