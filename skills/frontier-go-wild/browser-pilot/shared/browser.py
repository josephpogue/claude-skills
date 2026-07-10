"""Patchright launchers. Ephemeral for stateless skills, persistent for SSO."""
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from patchright.async_api import async_playwright, BrowserContext

REPO_ROOT = Path(__file__).resolve().parents[1]  # pilot root (vendored)
PROFILES_DIR = REPO_ROOT / ".browser-profiles"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1440, "height": 900}
LOCALE = "en-US"
TIMEZONE = "America/Los_Angeles"


@asynccontextmanager
async def launch_ephemeral(headless: bool = True) -> AsyncIterator[BrowserContext]:
    """Stateless browser for sites that don't require auth (Google Flights)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(
            user_agent=UA, viewport=VIEWPORT, locale=LOCALE, timezone_id=TIMEZONE,
        )
        try:
            yield ctx
        finally:
            await ctx.close()
            await browser.close()


@asynccontextmanager
async def launch_persistent(profile_name: str, headless: bool = False) -> AsyncIterator[BrowserContext]:
    """Persistent profile for sites that require auth (amex.point.me)."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile_dir = PROFILES_DIR / profile_name
    profile_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir), headless=headless,
            user_agent=UA, viewport=VIEWPORT, locale=LOCALE, timezone_id=TIMEZONE,
        )
        try:
            yield ctx
        finally:
            await ctx.close()
