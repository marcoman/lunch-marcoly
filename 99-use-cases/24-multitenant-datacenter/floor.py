"""Stand-in floor for the first presentation of 24-multitenant-datacenter.

Shared replicas are named for the region: usw1-1, use1-1, and so on.
us-east-1 has three. Everywhere else has two. Named customers are a fixed
stand-in so the rolling walk can show an empty datacenter and a dedicated
replica set. Placement rules come later.

The page does not evaluate flags yet. The Flags tab is a local stub.
LaunchDarkly: multi-context, one per size row, when the SDK is wired.
https://launchdarkly.com/docs/home/flags/multi-contexts
"""

from __future__ import annotations

import json
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parent
DELAY_MS = 1000
POPULATION = 1000

# us-west-1 is usw1. The digit is the AWS region number, not the replica.
REGION_CODE = {
    "us-west-1": "usw1",
    "us-east-1": "use1",
    "eu-central-1": "euc1",
    "eu-west-1": "euw1",
    "ap-southeast-1": "apse1",
    "ap-south-1": "aps1",
}

# Floor order is the rolling-deployment order. Shared replicas: us-east-1 has
# three, everywhere else has two. A large customer has one dedicated replica.
# ENZO in us-west-1 is the exception and keeps two.
DATACENTERS = (
    {"key": "us-west-1", "geo": "us", "gdpr": False, "replicas": 2, "customers": [
        {"name": "ENZO", "replicas": 2},
    ]},
    {"key": "us-east-1", "geo": "us", "gdpr": False, "replicas": 3, "customers": [
        {"name": "ACME", "replicas": 3},
        {"name": "HUDSON", "replicas": 1},
    ]},
    {"key": "eu-central-1", "geo": "eu", "gdpr": True, "replicas": 2, "customers": [
        {"name": "BIGCO", "replicas": 2},
        {"name": "RHEIN", "replicas": 1},
    ]},
    {"key": "eu-west-1", "geo": "eu", "gdpr": True, "replicas": 2, "customers": []},
    {"key": "ap-southeast-1", "geo": "ap", "gdpr": False, "replicas": 2, "customers": [
        {"name": "DREX", "replicas": 2},
        {"name": "KOPI", "replicas": 1},
    ]},
    {"key": "ap-south-1", "geo": "ap", "gdpr": False, "replicas": 2, "customers": []},
)

CAPABILITIES = (
    {"key": "security", "label": "sec"},
    {"key": "firewall", "label": "fw"},
    {"key": "data-sharing", "label": "share"},
    {"key": "marketing", "label": "mkt"},
)

# Five customers of each size. Display names stay within 15 characters.
# A single-tenant name is served by that customer's replicas.
PANEL = (
    {"name": "ACME CORP", "sizeClass": "small", "datacenter": "us-east-1", "tenancy": "single", "customer": "ACME"},
    {"name": "ENZO MEDIA", "sizeClass": "small", "datacenter": "us-west-1", "tenancy": "single", "customer": "ENZO"},
    {"name": "BHARAT RAIL", "sizeClass": "small", "datacenter": "ap-south-1", "tenancy": "multi"},
    {"name": "PACIFIC GRID", "sizeClass": "small", "datacenter": "us-west-1", "tenancy": "multi"},
    {"name": "FYRA LUFT", "sizeClass": "small", "datacenter": "eu-west-1", "tenancy": "multi"},
    {"name": "BIGCO HAUS", "sizeClass": "medium", "datacenter": "eu-central-1", "tenancy": "single", "customer": "BIGCO"},
    {"name": "BLEU NUAGES", "sizeClass": "medium", "datacenter": "eu-west-1", "tenancy": "multi"},
    {"name": "DREX MELAYU", "sizeClass": "medium", "datacenter": "ap-southeast-1", "tenancy": "single", "customer": "DREX"},
    {"name": "ORION DOCK", "sizeClass": "medium", "datacenter": "us-east-1", "tenancy": "multi"},
    {"name": "SAFFRON MILL", "sizeClass": "medium", "datacenter": "ap-south-1", "tenancy": "multi"},
    {"name": "HUDSON YARD", "sizeClass": "large", "datacenter": "us-east-1", "tenancy": "single", "customer": "HUDSON"},
    {"name": "RHEIN WERK", "sizeClass": "large", "datacenter": "eu-central-1", "tenancy": "single", "customer": "RHEIN"},
    {"name": "KOPI SINGA", "sizeClass": "large", "datacenter": "ap-southeast-1", "tenancy": "single", "customer": "KOPI"},
    {"name": "SIERRA PEAK", "sizeClass": "large", "datacenter": "us-west-1", "tenancy": "multi"},
    {"name": "LOTUS DELTA", "sizeClass": "large", "datacenter": "ap-south-1", "tenancy": "multi"},
)

SIZES = ("small", "medium", "large")


def replica_names(prefix: str, count: int) -> list[str]:
    """usw1-1..usw1-N, or ACME-1..ACME-N for one named customer."""
    return [f"{prefix}-{index}" for index in range(1, count + 1)]


def roll_steps() -> list[dict[str, str]]:
    """One datacenter at a time. Shared replicas, then each customer's replicas."""
    steps: list[dict[str, str]] = []
    for datacenter in DATACENTERS:
        key = datacenter["key"]
        count = datacenter["replicas"]
        for name in replica_names(REGION_CODE[key], count):
            steps.append({"datacenter": key, "replica": name, "tenancy": "multi"})
        for customer in datacenter["customers"]:
            for name in replica_names(customer["name"], customer["replicas"]):
                steps.append({
                    "datacenter": key,
                    "replica": name,
                    "tenancy": "single",
                    "customer": customer["name"],
                })
    return steps


def region_population() -> dict[str, int]:
    """1,000 customers. US 50%, EU 30%, AP 20%. ap-south-1 is 25% of AP.

    US and EU are split evenly across their two regions.
    """
    totals: dict[str, int] = {}
    groups = (
        (500, ("us-west-1", "us-east-1"), (1, 1)),
        (300, ("eu-central-1", "eu-west-1"), (1, 1)),
        (200, ("ap-southeast-1", "ap-south-1"), (3, 1)),
    )
    for share, keys, weights in groups:
        weight_sum = sum(weights)
        raw = [share * weight / weight_sum for weight in weights]
        counts = [int(value) for value in raw]
        left = share - sum(counts)
        order = sorted(range(len(raw)), key=lambda index: raw[index] - counts[index], reverse=True)
        for index in order:
            if left == 0:
                break
            counts[index] += 1
            left -= 1
        for key, count in zip(keys, counts):
            totals[key] = count
    return totals


def size_counts(total: int) -> dict[str, int]:
    """50% small, 30% medium, 15% large, 5% named. Integers sum to total."""
    weights = (("small", 50), ("medium", 30), ("large", 15), ("named", 5))
    raw = [(name, total * weight / 100) for name, weight in weights]
    counts = {name: int(value) for name, value in raw}
    left = total - sum(counts.values())
    order = sorted(raw, key=lambda item: item[1] - int(item[1]), reverse=True)
    for name, _value in order:
        if left == 0:
            break
        counts[name] += 1
        left -= 1
    return counts


def load_customizations() -> dict[str, object]:
    """Local customizations.json wins. The example file is the default.

    Same shape as 21-tenant-datacenters: a gitignored local file, and an
    example that ships with the lab.
    """
    local = EXAMPLE / "customizations.json"
    fallback = EXAMPLE / "customizations.json.example"
    path = local if local.is_file() else fallback
    if not path.is_file():
        return {"sharedReplicaIcon": "icons/shared.svg", "customerIcons": []}
    return json.loads(path.read_text())


def floor_payload() -> dict[str, object]:
    """Topology the page renders. Flag values are not included."""
    population = region_population()
    custom = load_customizations()
    return {
        "delayMs": DELAY_MS,
        "population": POPULATION,
        "sharedReplicaIcon": custom.get("sharedReplicaIcon", "icons/shared.svg"),
        "customerIcons": custom.get("customerIcons", []),
        "datacenters": [
            {
                "key": item["key"],
                "code": REGION_CODE[item["key"]],
                "geo": item["geo"],
                "gdpr": item["gdpr"],
                "instances": item["replicas"],
                "customers": [customer["name"] for customer in item["customers"]],
                "counts": size_counts(population[item["key"]]),
                "shared": replica_names(REGION_CODE[item["key"]], item["replicas"]),
                "dedicated": {
                    customer["name"]: replica_names(customer["name"], customer["replicas"])
                    for customer in item["customers"]
                },
            }
            for item in DATACENTERS
        ],
        "capabilities": list(CAPABILITIES),
        "sizes": list(SIZES),
        "panel": list(PANEL),
        "steps": roll_steps(),
        "palettes": ["none", "roygbiv", "contrast", "earth", "ocean", "color-vision-aware"],
    }
