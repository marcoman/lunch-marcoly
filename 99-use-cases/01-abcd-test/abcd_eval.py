"""LaunchDarkly evaluation for the ABCD navigation count label test."""

from __future__ import annotations

import os

from ldclient import Config, Context, LDClient
import ldclient

# LaunchDarkly capability: String flag evaluation for multivariate A/B/C/D test
# See: https://launchdarkly.com/docs/sdk/features/flag-types

FLAG_COUNT_LABEL = "configure-navigation-count-label"
DEFAULT_COUNT_LABEL = "Count"

VARIATION_VALUES = (
    "Count",
    "Move Count",
    "Moves",
    "Navigation Counts",
)

_client: LDClient | None = None


def init_client() -> LDClient | None:
    global _client
    if _client is not None:
        return _client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        return None
    ldclient.set_config(Config(sdk_key))
    _client = ldclient.get()
    return _client


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def evaluate_count_label(username: str) -> str:
    """Return the resolved navigation count label for a user context."""
    client = init_client()
    if client is None or not client.is_initialized():
        return DEFAULT_COUNT_LABEL
    context = Context.builder(username).build()
    return str(client.variation(FLAG_COUNT_LABEL, context, DEFAULT_COUNT_LABEL))
