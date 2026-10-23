"""Generate the 52 tenant placements for the datacenter lab.

Each presence is one tenant context. Version starts at 0 for every instance.
Later release flags will move instances from 0 through 9.

Contexts — https://launchdarkly.com/docs/home/flags/contexts
"""

from __future__ import annotations

from typing import Any

DATACENTERS = ("DC01", "DC02", "DC03", "DC04", "DC05")
VOWELS = frozenset("AEIOU")
UNKNOWN = frozenset("QZ")
PREFIX = {"large": "L", "medium": "M", "small": "S", "unknown": "U"}
# Every instance starts at version 0. Later flags release 1 through 9.
VERSION = 0


def size_class(letter: str) -> str:
    """Classify one A–Z letter as large, medium, small, or unknown.

    Vowels are Large. Q and Z are unknown. Otherwise
    ``(letter number - 1) % 3``: 2 is Medium, and 0 or 1 is Small.
    """
    number = ord(letter) - ord("A") + 1
    if letter in VOWELS:
        return "large"
    if letter in UNKNOWN:
        return "unknown"
    if (number - 1) % 3 == 2:
        return "medium"
    return "small"


def presence(kind: str, instance: int) -> tuple[int, int]:
    """How many datacenters this instance occupies, and the size drawn in each.

    Odd and even refer to the instance number inside the size class.
    Unknown stays in one datacenter at size 3.
    """
    odd = instance % 2 == 1
    if kind == "small":
        return (1, 1) if odd else (2, 2)
    if kind == "medium":
        return (1, 5) if odd else (3, 5)
    if kind == "large":
        return (3, 7) if odd else (5, 7)
    return (1, 3)


def build_customers() -> list[dict[str, Any]]:
    """Walk A–Z twice. One cursor hands out the next datacenters, wrapping after DC05."""
    counters = {key: 0 for key in PREFIX}
    customers: list[dict[str, Any]] = []
    cursor = 0
    for cycle in (1, 2):
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            kind = size_class(letter)
            counters[kind] += 1
            instance = counters[kind]
            span, size = presence(kind, instance)
            datacenters = [
                DATACENTERS[(cursor + offset) % len(DATACENTERS)] for offset in range(span)
            ]
            cursor += span
            customers.append(
                {
                    "name": f"{PREFIX[kind]}{instance:02d}",
                    "letter": letter,
                    "cycle": cycle,
                    "sizeClass": kind,
                    "size": size,
                    "version": VERSION,
                    "span": span,
                    "datacenters": datacenters,
                }
            )
    return customers


def evaluation_context(customer: dict[str, Any]) -> dict[str, Any]:
    """One context dict for the Contexts tab. This is not an SDK evaluation.

    A customer in three datacenters produces three of these, with the same
    key. tenant_context builds the SDK context from the same fields when
    evaluate_floor runs tenant-border-palette, tenant-box-fill, and
    tenant-security.

    LaunchDarkly: contexts — https://launchdarkly.com/docs/home/flags/contexts
    """
    return {
        "kind": "tenant",
        "key": customer["name"],
        "size": customer["size"],
        "sizeClass": customer["sizeClass"],
        "version": customer["version"],
        "span": customer["span"],
        "datacenter": customer["datacenter"],
    }


def placements(customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One box per datacenter a customer occupies. The name is repeated."""
    boxes = []
    for customer in customers:
        for datacenter in customer["datacenters"]:
            boxes.append(
                {
                    "name": customer["name"],
                    "letter": customer["letter"],
                    "cycle": customer["cycle"],
                    "sizeClass": customer["sizeClass"],
                    "size": customer["size"],
                    "version": customer["version"],
                    "span": customer["span"],
                    "datacenter": datacenter,
                }
            )
    return boxes


def build_layout() -> dict[str, Any]:
    """The dictionary of the whole floor, before either flag is evaluated.

    This process is pretending to be every application at once, which is
    why the dict holds all of them. datacenters groups the boxes the page
    draws. contexts is the matching list, one dict per presence.
    evaluate_floor walks the boxes and evaluates tenant-border-palette,
    tenant-box-fill, tenant-security, and tenant-firewall for each one. A security wave
    targets one name, a large presence in one datacenter, or the full
    deployment sequence.
    """
    customers = build_customers()
    boxes = placements(customers)
    grouped = []
    for datacenter in DATACENTERS:
        members = [box for box in boxes if box["datacenter"] == datacenter]
        grouped.append(
            {
                "name": datacenter,
                "customerCount": len(members),
                "customers": members,
            }
        )
    return {
        "datacenters": grouped,
        "contexts": [evaluation_context(box) for box in boxes],
    }
