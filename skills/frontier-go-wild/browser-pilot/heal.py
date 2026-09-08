"""Self-healing for a browser step whose stored selector stopped matching.

The reason this exists: when a site moves a button, the old behaviour was a
raised error, a dead run, and Joseph opening a new session to tell an agent
where the button went. Here the run repairs itself instead. It reads the page
the way a person would (session.tree()), works out which control is the one the
step meant, confirms that control is really there, completes the step, and
writes the new selector into recipes/<site>.json so the next run is
straight-through again.

Two hard limits:

* It never heals its way past a bot challenge, a locked account, or a rejected
  password. Those are a person's job, and pushing on them is exactly the
  behaviour that gets an account flagged. classify() sends them to Joseph.
* It never trusts a repair it has not confirmed on the live page. The proposed
  control has to exist in the page read and be visible before the step runs or
  anything is written back.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import recipes
import signals as signals_mod

RECIPES_DIR = Path(__file__).resolve().parent / "recipes"

HEAL, HUMAN, RETRY = "heal", "human", "retry"

# Page text that means a person is required. Checked before anything else: a
# selector timeout on a page that is showing a CAPTCHA is a CAPTCHA, not a
# moved button.
_HUMAN_PAGE = (
    ("captcha", "a CAPTCHA is on the page, only a person may answer it"),
    ("verify you are human", "a CAPTCHA is on the page, only a person may answer it"),
    ("i'm not a robot", "a CAPTCHA is on the page, only a person may answer it"),
    ("are you a robot", "a CAPTCHA is on the page, only a person may answer it"),
    ("unusual traffic", "the site is showing a bot challenge"),
    ("account has been locked", "account locked"),
    ("account is locked", "account locked"),
    ("account has been suspended", "account suspended"),
    ("too many failed", "too many attempts"),
    ("too many attempts", "too many attempts"),
    ("password you entered is incorrect", "wrong password"),
    ("incorrect password", "wrong password"),
    ("invalid username or password", "wrong password"),
    ("invalid credentials", "wrong password"),
)

_HUMAN_ERROR = (
    ("captcha", "a CAPTCHA blocked the step"),
    ("needs_human", "the recipe says this site needs a person"),
    ("403", "the site refused the request"),
)

# A blip, not a layout change. Trying to rewrite a selector here would replace a
# good selector with whatever happened to be on an error page.
_RETRY_ERROR = (
    ("net::", "the site did not respond"),
    ("err_connection", "the site did not respond"),
    ("err_name_not_resolved", "the site did not resolve"),
    ("econnreset", "the connection dropped"),
    ("502", "the site returned a server error"),
    ("503", "the site returned a server error"),
    ("504", "the site returned a server error"),
    ("429", "the site is rate limiting"),
    ("navigation timeout", "the page did not load"),
)

# The break this whole module is for: the step was fine, the control moved.
_HEAL_ERROR = (
    ("waiting for locator", "a stored selector stopped matching"),
    ("waiting for selector", "a stored selector stopped matching"),
    ("no element matches", "a stored selector stopped matching"),
    ("element is not visible", "the control is on the page but hidden"),
    ("not visible", "the control is on the page but hidden"),
    ("strict mode violation", "the stored selector now matches more than one control"),
    ("timeouterror", "a stored selector stopped matching"),
    ("selector resolved to hidden", "the control is on the page but hidden"),
)


@dataclass
class Verdict:
    action: str   # heal | human | retry
    reason: str


def classify(error: str, page_text: str = "") -> Verdict:
    """Decide whether a failed step may be repaired automatically."""
    page = (page_text or "").lower()
    for needle, why in _HUMAN_PAGE:
        if needle in page:
            return Verdict(HUMAN, why)
    err = (error or "").lower()
    for needle, why in _HUMAN_ERROR:
        if needle in err:
            return Verdict(HUMAN, why)
    for needle, why in _RETRY_ERROR:
        if needle in err:
            return Verdict(RETRY, why)
    for needle, why in _HEAL_ERROR:
        if needle in err:
            return Verdict(HEAL, why)
    # Anything unfamiliar goes to a person. Guessing is worse than stopping.
    return Verdict(HUMAN, "the failure was not one this can recognise")


# ---- asking for the replacement control ------------------------------------

_PROMPT = """A browser automation step just failed because a stored selector no
longer matches anything on the page. Your job is to say which control on the
page now does what that step meant to do.

Site: {site}
Step: {intent}
Selector that stopped working: {old}
Error: {error}

Every visible control on the page right now, one section per frame:

{tree}

Reply with ONLY the id in square brackets of the control that does what the step
meant, for example: 0-12
If nothing on this page does it, reply with exactly: none
Never pick a control that would submit a bot challenge, a security check, or a
"verify you are human" widget; reply none instead."""


def ask_claude(prompt: str, timeout_s: int = 180) -> str:
    """Put the page read in front of a model and take back one element id."""
    out = subprocess.run(
        ["claude", "-p", "--model", "sonnet", prompt],
        capture_output=True, text=True, timeout=timeout_s,
    )
    if out.returncode != 0:
        raise RuntimeError(f"claude -p failed: {(out.stderr or '').strip()[:200]}")
    return out.stdout.strip()


def _element_id(reply: str) -> str:
    """Take the id out of whatever the model actually said."""
    text = (reply or "").strip().strip("`").strip()
    for token in text.replace("[", " ").replace("]", " ").split():
        head, _, tail = token.partition("-")
        if head.isdigit() and tail.isdigit():
            return f"{head}-{tail}"
    return ""


# ---- showing it on the dashboard -------------------------------------------

def runlog_progress(label: str, run_id: str | None = None) -> None:
    """Put a line on the run's Mission Control card while it is still running.

    A heal that Joseph only finds out about by reading a log file is not much
    better than a break. This says it on the card, live, without stopping him
    to ask anything."""
    rid = run_id or os.environ.get("BROWSER_PILOT_RUN_ID")
    if not rid:
        return
    try:
        subprocess.run(["runlog", "progress", rid, label],
                       check=False, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


# ---- telling a person ------------------------------------------------------

_GOG = "/opt/homebrew/bin/gog"
_RECIPIENT = "josephpogue22@gmail.com"


def notify_human(alert: dict) -> None:
    """Email Joseph, and fall back to a macOS banner if mail cannot go out.

    Same two channels the Amex CAPTCHA notice uses, for the same reason: an
    unattended run that stops silently looks identical to one that never ran."""
    body = alert["body"] + (f"\n\nScreenshot: {alert['screenshot']}\n"
                            if alert.get("screenshot") else "\n")
    if Path(_GOG).exists():
        try:
            subprocess.run(
                [_GOG, "gmail", "send", "--account", _RECIPIENT, "--to", _RECIPIENT,
                 "--subject", alert["subject"], "--body", body, "--no-input"],
                check=True, capture_output=True, timeout=60,
            )
            return
        except Exception:
            pass
    try:
        subprocess.run(
            ["/usr/bin/osascript", "-e",
             f'display notification "{alert["subject"]}" with title "browser-pilot"'],
            check=False, timeout=10,
        )
    except Exception:
        pass


# ---- writing the repair back -----------------------------------------------

def write_back(recipe_path: str | Path, key: str, old: str, new: str,
               intent: str, when: str | None = None) -> dict:
    """Store the repaired selector, and say in the recipe that it was repaired.

    The dated note matters as much as the selector: a recipe that quietly
    rewrites itself gives Joseph no way to see the site is drifting."""
    recipe = recipes.load(recipe_path)
    recipe.setdefault("selectors", {})[key] = new
    day = when or time.strftime("%Y-%m-%d")
    recipe.setdefault("gotchas", []).append(
        f"{day} self-healed: '{key}' no longer matched {old or '(nothing stored)'}; "
        f"now {new} (the control for: {intent})."
    )
    recipes.save(recipe, recipe_path)
    return recipe


def recipe_path_for(site: str, recipes_dir: str | Path | None = None) -> Path:
    return Path(recipes_dir or RECIPES_DIR) / f"{site}.json"


def intent_for(recipe: dict, key: str) -> str:
    """What the step means, in words, so a moved control can be recognised.

    A selector says where a control was, never what it was for, so it is useless
    once the page changes. A recipe can carry the words itself under `intents`,
    which is what lets an existing scraper heal without changing its code. If it
    does not, the selector's own name is the next best thing."""
    stored = (recipe.get("intents") or {}).get(key)
    if stored:
        return stored
    return f"the control the recipe calls '{key}'"


# ---- the repair ------------------------------------------------------------

async def _page_text(session, tree_text: str = "") -> str:
    """Everything readable on the page, for classify() to judge.

    The control list alone is not enough: "Verify you are human" is usually a
    paragraph, and a reCAPTCHA lives in a cross-origin frame whose body cannot
    be read at all. Frame titles come through in the tree text, which is how a
    frame named reCAPTCHA still gets caught."""
    parts = [tree_text]
    for frame in session.page.frames:
        try:
            parts.append(await frame.inner_text("body"))
        except Exception:
            continue
    return "\n".join(p for p in parts if p)



async def heal_step(
    session,
    *,
    site: str,
    key: str,
    error: str,
    intent: str = "",
    method: str = "click",
    value: str | None = None,
    recipe_path: str | Path | None = None,
    recipes_dir: str | Path | None = None,
    ask: Callable[[str], str] | None = None,
    alert: Callable[[dict], Any] | None = None,
    run_id: str | None = None,
    signals_dir: str | Path | None = None,
    screenshot_dir: str | Path | None = None,
) -> dict:
    """Repair one broken step in place and complete it. Never raises."""
    ask = ask or ask_claude
    alert = alert or notify_human
    path = Path(recipe_path) if recipe_path else recipe_path_for(site, recipes_dir)

    def record(event: str, **fields) -> None:
        if run_id and signals_dir:
            signals_mod.emit(run_id, event, signals_dir, site=site, key=key, **fields)

    async def give_up(reason: str, action: str) -> dict:
        shot = None
        if screenshot_dir:
            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            shot = str(Path(screenshot_dir) / f"heal-{site}-{key}-{int(time.time())}.png")
            try:
                await session.screenshot(shot)
            except Exception:
                shot = None
        record("heal_failed", reason=reason, action=action, screenshot=shot)
        runlog_progress(f"could not fix {site}: '{key}' -- {reason}", run_id)
        alert({
            "subject": f"browser-pilot could not fix {site}: {key}",
            "body": (f"The step '{intent}' failed on {site} and could not be "
                     f"repaired automatically.\n\nWhy: {reason}\nError: {error}"),
            "site": site, "key": key, "reason": reason, "screenshot": shot,
        })
        return {"healed": False, "action": action, "reason": reason, "screenshot": shot}

    try:
        page = await session.tree()
    except Exception as e:
        return await give_up(f"the page could not be read ({type(e).__name__})", HUMAN)

    verdict = classify(error, await _page_text(session, page["tree"]))
    if verdict.action != HEAL:
        return await give_up(verdict.reason, verdict.action)

    old = ""
    try:
        stored = recipes.load(path)
        old = (stored.get("selectors") or {}).get(key, "")
        intent = intent or intent_for(stored, key)
    except Exception:
        intent = intent or f"the control the recipe calls '{key}'"

    try:
        reply = ask(_PROMPT.format(site=site, intent=intent, old=old or "(none)",
                                   error=error, tree=page["tree"]))
    except Exception as e:
        return await give_up(f"the page read could not be reviewed ({type(e).__name__})", HUMAN)

    eid = _element_id(reply)
    chosen = next((e for e in page["elements"] if e["id"] == eid), None)
    if not chosen:
        return await give_up("no control on the page was identified as the one that moved", HUMAN)

    # Confirm the repair on the live page before trusting it. A selector that
    # cannot be seen is not a fix, it is a second break stored in the recipe.
    try:
        frame = session.page.frames[chosen["frame"]]
        if not await frame.is_visible(chosen["selector"]):
            return await give_up("the replacement control was not visible on the page", HUMAN)
    except Exception as e:
        return await give_up(f"the replacement selector did not resolve ({type(e).__name__})", HUMAN)

    try:
        await session.act(chosen["id"], method, value)
    except Exception as e:
        return await give_up(f"the repaired step still failed ({type(e).__name__}: {e})", HUMAN)

    try:
        write_back(path, key, old, chosen["selector"], intent)
    except Exception as e:
        # The step went through; only the memory of it failed. Say so rather
        # than reporting a clean heal that will break again next run.
        record("heal_not_saved", was=old, now=chosen["selector"], error=str(e))
        return {"healed": True, "saved": False, "action": HEAL,
                "selector": chosen["selector"], "was": old, "element_id": chosen["id"],
                "name": chosen["name"], "reason": f"repair not written to {path}: {e}"}

    record("healed", was=old, now=chosen["selector"], name=chosen["name"],
           element_id=chosen["id"], intent=intent)
    runlog_progress(f"healed {site}: '{key}' moved from {old or '(nothing stored)'} "
                    f"to {chosen['selector']} ({chosen['name']})", run_id)
    return {"healed": True, "saved": True, "action": HEAL,
            "selector": chosen["selector"], "was": old, "element_id": chosen["id"],
            "name": chosen["name"], "reason": verdict.reason}


def main() -> int:
    """Classify a failure from the command line, for a shell-driven automation."""
    import argparse
    p = argparse.ArgumentParser(description="classify a browser-pilot failure")
    p.add_argument("--error", required=True)
    p.add_argument("--page-text", default="")
    a = p.parse_args()
    v = classify(a.error, a.page_text)
    print(json.dumps({"action": v.action, "reason": v.reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
