"""Long-lived Patchright browser session exposing agent-drivable primitives.

The deterministic engines and the browser-pilot agent both drive a page
through this class. It owns its own playwright/context lifecycle (unlike
shared/browser.py's context managers) so the daemon can keep one page alive
across many client calls."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from patchright.async_api import async_playwright
from shared.profiles import UA, VIEWPORT, LOCALE, TIMEZONE, PROFILES_DIR, profile_dir

_CONTROL_SELECTOR = "a, button, input, select, textarea, [role=button]"

# How much page text a snapshot returns. The old 4000 was small enough to cut
# real content off the end of a long results grid -- and because the cut was
# silent, a caller could not tell a short page from a truncated one. Frontier's
# Go Wild grid alone runs past 4000 on a busy route. Raise the default and set
# `truncated` when the cut actually happens; override per-machine with
# BROWSER_PILOT_MAX_TEXT.
_MAX_TEXT = int(os.environ.get("BROWSER_PILOT_MAX_TEXT") or 20000)

# What tree() considers a control. Wider than _CONTROL_SELECTOR because the
# healer has to find things a scraper never touched: ARIA widgets and rich-text
# boxes that carry no <input> at all.
_TREE_SELECTOR = (
    "a, button, input:not([type=hidden]), select, textarea, summary, "
    "[role=button], [role=link], [role=checkbox], [role=radio], [role=tab], "
    "[role=textbox], [role=combobox], [role=menuitem], [contenteditable=true]"
)

# A cap so a huge page cannot blow up a daemon reply. Unlike snapshot()'s old
# silent slice, hitting it sets `truncated`.
_MAX_ELEMENTS = int(os.environ.get("BROWSER_PILOT_MAX_ELEMENTS") or 300)

# Runs once per frame. Kept as in-page JavaScript rather than CDP so it works
# under Patchright and inside every frame Playwright can reach.
_COLLECT_JS = r"""([sel, max]) => {
  const esc = (s) => (window.CSS && CSS.escape) ? CSS.escape(s) : String(s).replace(/[^a-zA-Z0-9_-]/g, '\\$&');

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none') return false;
    if (parseFloat(st.opacity || '1') === 0) return false;
    if (el.closest('[aria-hidden="true"]')) return false;
    return true;
  };

  const clean = (t) => (t || '').replace(/\s+/g, ' ').trim().slice(0, 120);

  const nameOf = (el) => {
    const aria = clean(el.getAttribute('aria-label'));
    if (aria) return aria;
    const lb = el.getAttribute('aria-labelledby');
    if (lb) {
      const n = clean(lb.split(/\s+/).map(i => {
        const t = document.getElementById(i); return t ? t.innerText : '';
      }).join(' '));
      if (n) return n;
    }
    if (el.id) {
      const l = document.querySelector('label[for="' + esc(el.id) + '"]');
      if (l) { const n = clean(l.innerText); if (n) return n; }
    }
    const wrap = el.closest('label');
    if (wrap) { const n = clean(wrap.innerText); if (n) return n; }
    const ph = clean(el.getAttribute('placeholder'));
    if (ph) return ph;
    const txt = clean(el.innerText);
    if (txt) return txt;
    const title = clean(el.getAttribute('title'));
    if (title) return title;
    const alt = clean(el.getAttribute('alt'));
    if (alt) return alt;
    return clean(el.getAttribute('name'));
  };

  const roleOf = (el) => {
    const explicit = el.getAttribute('role');
    if (explicit) return explicit;
    const tag = el.tagName.toLowerCase();
    if (tag === 'a') return el.hasAttribute('href') ? 'link' : 'generic';
    if (tag === 'button') return 'button';
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'summary') return 'disclosure';
    if (tag === 'input') {
      const t = (el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      if (t === 'submit' || t === 'button' || t === 'reset') return 'button';
      if (t === 'password') return 'password';
      return 'textbox';
    }
    return 'generic';
  };

  // A selector durable enough to store in a recipe: an id when it is unique,
  // otherwise a structural path.
  const selectorFor = (el) => {
    if (el.id && document.querySelectorAll('#' + esc(el.id)).length === 1) {
      return '#' + esc(el.id);
    }
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur.tagName.toLowerCase() !== 'html') {
      let part = cur.tagName.toLowerCase();
      const parent = cur.parentElement;
      if (parent) {
        const sibs = [...parent.children].filter(c => c.tagName === cur.tagName);
        if (sibs.length > 1) part += ':nth-of-type(' + (sibs.indexOf(cur) + 1) + ')';
      }
      parts.unshift(part);
      cur = parent;
    }
    return parts.join(' > ');
  };

  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    if (out.length >= max) break;
    if (!visible(el)) continue;
    const isInput = el.tagName === 'INPUT' || el.tagName === 'TEXTAREA';
    const type = (el.getAttribute('type') || '').toLowerCase();
    out.push({
      n: out.length,
      role: roleOf(el),
      name: nameOf(el),
      value: (isInput && type !== 'password') ? clean(el.value) : '',
      selector: selectorFor(el),
      tag: el.tagName.toLowerCase(),
    });
  }
  return out;
}"""


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
        # id -> element record, refreshed by tree() and read by act().
        self._tree_index: dict[str, dict] = {}

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        user_data = profile_dir(self.profile)
        user_data.mkdir(parents=True, exist_ok=True)
        self.ctx = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(user_data), headless=self.headless,
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
        full_text = await self.page.inner_text("body")
        text = full_text[:_MAX_TEXT]
        truncated = len(full_text) > _MAX_TEXT
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
        return {
            "url": self.page.url,
            "title": title,
            "text": text,
            "truncated": truncated,
            "textLength": len(full_text),
            "controls": controls,
        }

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

    async def pages(self) -> list[dict]:
        """Every tab this context holds, with the active one marked.

        A site that hands off to an affiliated portal (Schwab -> Retirement Plan
        Services) opens a NEW tab, and the daemon keeps driving the old one. The
        page looks unchanged and the handoff looks broken; it is not, it is in a
        tab nothing was pointing at.
        """
        out = []
        for i, pg in enumerate(self.ctx.pages):
            out.append({"index": i, "url": pg.url, "title": await pg.title(),
                        "active": pg is self.page})
        return out

    async def use_page(self, n: int) -> str:
        """Drive the nth tab from now on (see pages())."""
        pgs = self.ctx.pages
        if n >= len(pgs):
            return f"index out of range: {len(pgs)} page(s)"
        self.page = pgs[n]
        await self.page.bring_to_front()
        return self.page.url

    async def evaluate(self, expression: str) -> Any:
        """Run arbitrary JavaScript on the page and return the result."""
        return await self.page.evaluate(expression)

    # ---- accessibility tree -------------------------------------------------
    # snapshot() above returns page text plus the first 100 controls named by tag
    # and id. It cannot see inside an iframe, and it cannot tell a visible control
    # from a hidden twin, which is the exact shape of the breaks that keep needing
    # a human. tree() is what the healer reads instead: every *visible* control in
    # every frame, named the way a person would read it, each with a stable id to
    # act on and a selector durable enough to write back into a recipe.

    async def tree(self) -> dict[str, Any]:
        """Every visible control on the page, one section per frame."""
        elements: list[dict[str, Any]] = []
        index: dict[str, dict[str, Any]] = {}
        lines: list[str] = []
        truncated = False

        for fi, frame in enumerate(self.page.frames):
            try:
                found = await frame.evaluate(_COLLECT_JS, [_TREE_SELECTOR, _MAX_ELEMENTS])
            except Exception:
                # A cross-origin or torn-down frame simply contributes nothing.
                continue
            if not found:
                continue
            truncated = truncated or len(found) >= _MAX_ELEMENTS
            lines.append(f"=== Frame {fi} ({await self._frame_label(fi, frame)}) ===")
            for e in found:
                eid = f"{fi}-{e['n']}"
                rec = {
                    "id": eid,
                    "role": e["role"],
                    "name": e["name"],
                    "value": e["value"],
                    "frame": fi,
                    "selector": e["selector"],
                    "tag": e["tag"],
                }
                elements.append(rec)
                index[eid] = rec
                val = f" = {e['value']}" if e["value"] else ""
                lines.append(f"  [{eid}] {e['role']}: {e['name']}{val}")

        self._tree_index = index
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "tree": "\n".join(lines),
            "elements": elements,
            "count": len(elements),
            "truncated": truncated,
        }

    async def _frame_label(self, fi: int, frame) -> str:
        if fi == 0:
            return "Main"
        try:
            fe = await frame.frame_element()
            for attr in ("title", "name", "id"):
                v = await fe.get_attribute(attr)
                if v:
                    return v
        except Exception:
            pass
        return (frame.url or "iframe")[:60]

    async def act(self, element_id: str, method: str = "click",
                  value: str | None = None, timeout_ms: int = 5000) -> str:
        """Drive a control by the id tree() gave it.

        Unknown ids raise instead of guessing: a healer that silently acts on the
        wrong control is worse than one that stops and says the page moved."""
        entry = self._tree_index[element_id]
        frame = self.page.frames[entry["frame"]]
        loc = frame.locator(entry["selector"]).first
        m = method.lower()
        if m == "click":
            await loc.click(timeout=timeout_ms)
        elif m == "fill":
            await loc.fill(value or "", timeout=timeout_ms)
        elif m == "type":
            await loc.click(timeout=timeout_ms)
            await frame.page.keyboard.type(value or "", delay=50)
        elif m == "press":
            await loc.press(value or "Enter", timeout=timeout_ms)
        elif m == "select":
            await loc.select_option(value, timeout=timeout_ms)
        elif m == "check":
            await loc.check(timeout=timeout_ms)
        elif m == "uncheck":
            await loc.uncheck(timeout=timeout_ms)
        elif m == "hover":
            await loc.hover(timeout=timeout_ms)
        elif m == "wait":
            # Nothing is driven: the caller only needed the control to be there.
            await loc.wait_for(state="visible", timeout=timeout_ms)
        else:
            raise ValueError(f"unknown act method: {method}")
        return f"{m} {element_id} ({entry['name'] or entry['selector']})"
