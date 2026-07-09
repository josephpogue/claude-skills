"""Long-lived Patchright browser session exposing agent-drivable primitives.

The deterministic engines and the browser-pilot agent both drive a page
through this class. It owns its own playwright/context lifecycle (unlike
shared.browser's context managers) so the daemon can keep one page alive
across many client calls."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from patchright.async_api import async_playwright
from shared.browser import UA, VIEWPORT, LOCALE, TIMEZONE, PROFILES_DIR

_CONTROL_SELECTOR = "a, button, input, select, textarea, [role=button]"


class BrowserSession:
    def __init__(self, profile: str = "default", headless: bool = True, state_file: str | None = None):
        self.profile = profile
        self.headless = headless
        # A persistent profile drops session cookies across processes, so a fresh
        # (e.g. headless Mission Control) run starts logged out. state_file persists
        # the storage state (cookies) to disk so the session survives across runs:
        # save_state() after login, and start() re-injects it.
        self.state_file = Path(state_file).expanduser() if state_file else None
        self._pw = None
        self.ctx = None
        self.page = None

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        profile_dir = PROFILES_DIR / self.profile
        profile_dir.mkdir(parents=True, exist_ok=True)
        self.ctx = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir), headless=self.headless,
            user_agent=UA, viewport=VIEWPORT, locale=LOCALE, timezone_id=TIMEZONE,
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else await self.ctx.new_page()
        await self._restore_state()
        self._route_cache: dict[str, dict] = {}

    async def cache_route(self, pattern: str) -> str:
        """Intercept requests matching pattern: let the first call through to the real server,
        cache its response, and replay the cache for all subsequent identical requests.
        Useful for rate-limited APIs that only allow one call per session (e.g. geocoding)."""
        async def handle(route):
            url = route.request.url
            if url in self._route_cache:
                cached = self._route_cache[url]
                await route.fulfill(
                    status=cached["status"],
                    body=cached["body"],
                    headers={"content-type": cached.get("content_type", "application/json")},
                )
                return
            resp = await route.fetch()
            body = await resp.body()
            self._route_cache[url] = {
                "status": resp.status,
                "body": body,
                "content_type": resp.headers.get("content-type", "application/json"),
            }
            await route.fulfill(response=resp)

        await self.page.route(pattern, handle)
        return f"route cache active for: {pattern}"

    async def _restore_state(self) -> None:
        if not (self.state_file and self.state_file.exists()):
            return
        try:
            cookies = json.loads(self.state_file.read_text()).get("cookies") or []
        except (ValueError, OSError):
            return
        if cookies:
            await self.ctx.add_cookies(cookies)

    async def save_state(self) -> str:
        """Persist the current session (cookies + origins) to state_file."""
        if not self.state_file:
            raise RuntimeError("BrowserSession has no state_file configured")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        state = await self.ctx.storage_state()
        self.state_file.write_text(json.dumps(state))
        return str(self.state_file)

    async def stop(self) -> None:
        if self.ctx:
            await self.ctx.close()
            self.ctx = None
        self.page = None
        if self._pw:
            await self._pw.stop()
            self._pw = None

    async def open(self, url: str) -> str:
        await self.page.goto(url, wait_until="domcontentloaded")
        return self.page.url

    async def snapshot(self) -> dict[str, Any]:
        title = await self.page.title()
        text = (await self.page.inner_text("body"))[:4000]
        controls = await self.page.eval_on_selector_all(
            _CONTROL_SELECTOR,
            """els => els.slice(0, 100).map(e => ({
                tag: e.tagName.toLowerCase(),
                type: e.getAttribute('type') || '',
                id: e.id || '',
                name: e.getAttribute('name') || '',
                text: (e.innerText || e.value || '').trim().slice(0, 80),
                placeholder: e.getAttribute('placeholder') || '',
                href: e.getAttribute('href') || ''
            }))""",
        )
        return {"url": self.page.url, "title": title, "text": text, "controls": controls}

    async def click(self, selector: str, timeout_ms: int = 5000) -> None:
        await self.page.click(selector, timeout=timeout_ms)

    async def type(self, selector: str, value: str, timeout_ms: int = 5000) -> None:
        await self.page.fill(selector, value, timeout=timeout_ms)

    async def keyboard_type(self, selector: str, value: str, delay_ms: int = 50, timeout_ms: int = 5000) -> None:
        """Focus an element then type character-by-character via keyboard events.
        More reliable than fill() for web components that intercept synthetic events."""
        await self.page.click(selector, timeout=timeout_ms)
        # Triple-click to select existing content, then overwrite
        await self.page.click(selector, click_count=3, timeout=timeout_ms)
        await self.page.keyboard.type(value, delay=delay_ms)

    async def press(self, selector: str, key: str, timeout_ms: int = 5000) -> None:
        await self.page.press(selector, key, timeout=timeout_ms)

    async def wait(self, selector: str, timeout_ms: int = 5000) -> bool:
        await self.page.wait_for_selector(selector, timeout=timeout_ms, state="visible")
        return True

    async def screenshot(self, path: str, full_page: bool = True) -> str:
        await self.page.screenshot(path=path, full_page=full_page)
        return path

    async def focus_nth(self, tag: str, n: int) -> str:
        """Focus the nth element matching tag (0-indexed) by traversing the DOM, piercing shadow roots."""
        result = await self.page.evaluate(
            """([tag, n]) => {
                const els = [...document.querySelectorAll(tag)];
                if (n >= els.length) return 'index out of range: ' + els.length;
                const el = els[n];
                const inp = el.shadowRoot ? el.shadowRoot.querySelector('input,select,textarea') : el;
                if (!inp) return 'no focusable child';
                inp.focus(); inp.click(); inp.select && inp.select();
                return 'focused: ' + tag + '[' + n + '] value=' + inp.value;
            }""",
            [tag, n]
        )
        return result

    async def type_focused(self, value: str, delay_ms: int = 50) -> None:
        """Type text into whatever element is currently focused (use after focus_nth)."""
        await self.page.keyboard.type(value, delay=delay_ms)

    async def select(self, selector: str, value: str, timeout_ms: int = 5000) -> str:
        """Select an option from a select element by value. Pierces shadow DOM via JS."""
        result = await self.page.evaluate(
            """([selector, value]) => {
                const host = document.querySelector(selector);
                if (!host) return 'host not found: ' + selector;
                // Try direct select
                if (host.tagName === 'SELECT') {
                    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
                    setter.call(host, value);
                    host.dispatchEvent(new Event('change', {bubbles: true}));
                    host.dispatchEvent(new Event('input', {bubbles: true}));
                    return 'direct: ' + host.value;
                }
                // Pierce shadow root
                const sr = host.shadowRoot;
                if (!sr) return 'no shadow root';
                const sel = sr.querySelector('select');
                if (!sel) return 'no select in shadow';
                const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
                setter.call(sel, value);
                sel.dispatchEvent(new Event('change', {bubbles: true}));
                sel.dispatchEvent(new Event('input', {bubbles: true}));
                // Also dispatch on the host element for Angular
                host.dispatchEvent(new Event('change', {bubbles: true}));
                return 'shadow: ' + sel.value;
            }""",
            [selector, value]
        )
        return result

    async def select_native(self, selector: str, value: str, n: int = 0, timeout_ms: int = 5000) -> str:
        """Select an option using Playwright's native select_option (fires real browser events
        that Angular's ControlValueAccessor recognizes). Supports Playwright shadow-piercing
        selectors like 'bolt-select >> select'. Use n (0-indexed) when selector matches
        multiple elements, e.g. n=1 picks the second matching element."""
        try:
            loc = self.page.locator(selector).nth(n)
            await loc.select_option(value, timeout=timeout_ms)
            return f"selected: {value} at nth={n}"
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"

    async def evaluate(self, expression: str) -> Any:
        """Run arbitrary JavaScript on the page and return the result."""
        return await self.page.evaluate(expression)
