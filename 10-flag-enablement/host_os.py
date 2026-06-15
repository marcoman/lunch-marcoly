"""Host OS detection and emoji mapping for private-attribute flag evaluation."""

from __future__ import annotations

import platform

# LaunchDarkly capability: Private context attributes (server-side SDK)
# hostOs is used for targeting but redacted from events sent to LaunchDarkly.
# See: https://launchdarkly.com/docs/sdk/features/private-attributes

HOST_OS_ATTR = "hostOs"
FLAG_OS_EMOJI = "show-host-os-emoji"

OS_EMOJI = {
    "linux": "🐧",
    "macos": "🍎",
    "windows": "🪟",
    "other": "😊",
}


def detect_host_os() -> str:
    system = platform.system().lower()
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    return "other"


def os_emoji_for(host_os: str, show_os_emoji: bool) -> str:
    if not show_os_emoji:
        return ""
    return OS_EMOJI.get(host_os, OS_EMOJI["other"])


def build_evaluation_context(username: str):
    """Build an LD context with private hostOs for flag evaluation."""
    from ldclient import Context

    host_os = detect_host_os()
    context = (
        Context.builder(username)
        .set(HOST_OS_ATTR, host_os)
        .private(HOST_OS_ATTR)
        .build()
    )
    return context, host_os
