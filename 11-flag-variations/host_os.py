"""Host OS detection and anonymous-context evaluation for flag variations."""

from __future__ import annotations

import platform

# LaunchDarkly capability: Anonymous contexts + private attributes
# Anonymous flag uses a dedicated context; hostOs is private for targeting.
# See: https://launchdarkly.com/docs/sdk/features/anonymous
# See: https://launchdarkly.com/docs/sdk/features/private-attributes

HOST_OS_ATTR = "hostOs"
ANONYMOUS_CONTEXT_KEY = "anonymous"
FLAG_ANON_OS_EMOJI = "show-anonymous-host-os-emoji"

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


def build_anonymous_context():
    """Build anonymous LD context with private hostOs."""
    from ldclient import Context

    host_os = detect_host_os()
    context = (
        Context.builder(ANONYMOUS_CONTEXT_KEY)
        .anonymous(True)
        .set(HOST_OS_ATTR, host_os)
        .private(HOST_OS_ATTR)
        .build()
    )
    return context, host_os


def build_user_context(username: str):
    """Build logged-in user context for string/number/JSON flags."""
    from ldclient import Context

    return Context.builder(username).build()
