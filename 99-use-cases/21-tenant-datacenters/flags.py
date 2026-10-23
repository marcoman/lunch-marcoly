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

# Four hues per palette, one per size class. Each set stays dark enough that a
# 45% fill still leaves the light tenant name readable.
# ROYGBIV skips yellow and orange for that reason.
# Contrast replaces grays: a gray ramp has no hue to separate.
# Earth and ocean keep a theme, with the four size classes far apart on the wheel.
# Color-vision aware uses four Okabe–Ito hues. They stay distinct for the common
# red-green deficiencies and for typical color vision. They do not cover every type.
# https://jfly.uni-koeln.de/color/
PALETTES: dict[str, dict[str, str]] = {
    "roygbiv": {
        "small": "#3b82f6",
        "medium": "#22c55e",
        "large": "#ef4444",
        "unknown": "#a78bfa",
    },
    "contrast": {
        "small": "#06b6d4",
        "medium": "#eab308",
        "large": "#db2777",
        "unknown": "#a3e635",
    },
    "earth": {
        "small": "#84cc16",
        "medium": "#f59e0b",
        "large": "#be123c",
        "unknown": "#0284c7",
    },
    "ocean": {
        "small": "#2563eb",
        "medium": "#fb7185",
        "large": "#14b8a6",
        "unknown": "#fbbf24",
    },
    "color-vision-aware": {
        "small": "#56b4e9",
        "medium": "#e69f00",
        "large": "#009e73",
        "unknown": "#cc79a7",
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
