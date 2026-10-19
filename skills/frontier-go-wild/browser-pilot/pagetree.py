"""The page read shared by the async session and the sync replay.

Why it is its own module: session.tree() is async (the daemon) and replay.py is
sync (the lab drivers), but both must read a page the same way, or a repair the
replay makes would name controls the session would not. Keeping the in-page
JavaScript and its two limits in one file is what stops them drifting apart."""
from __future__ import annotations
import os

# What tree() considers a control. Wider than session.py's _CONTROL_SELECTOR because the
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
