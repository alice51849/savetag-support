#!/usr/bin/env python3
"""Build the SaveTag support site.

Merges src/locales/*.json and src/terms/*.json into three fully
self-contained pages:
  index.html   -> support + FAQ
  privacy.html -> privacy policy
  terms.html   -> terms of use

Each page carries inline CSS, inline JS and only the locale strings that page
needs. No external requests of any kind are emitted.

Authoring note: every locale states its one-sentence summary once, in "foot".
The builder copies it into both pages' meta description and into the privacy
lead, so the promise can never drift between places.
"""
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# The 50 Apple product-page locales — the same set the app declares in
# CFBundleLocalizations. The renderer resolves any other tag to the closest
# one of these (English last), so ?lang=<anything> renders a readable page.
LOCALES = [
    "en-US", "zh-Hant", "zh-Hans", "ja", "ko", "de-DE", "fr-FR", "fr-CA",
    "es-ES", "es-MX", "it", "pt-BR", "pt-PT", "nl-NL", "sv", "da", "fi",
    "no", "ru", "pl", "tr", "cs", "sk", "hr", "hu", "ro", "uk", "el", "ca",
    "sl-SI", "en-GB", "en-AU", "en-CA", "ar-SA", "he", "hi", "th", "vi",
    "id", "ms", "bn-BD", "gu-IN", "kn-IN", "ml-IN", "mr-IN", "or-IN",
    "pa-IN", "ta-IN", "te-IN", "ur-PK",
]
PENDING = []
RTL = {"ar-SA", "he", "ur-PK"}
SITE = "https://alice51849.github.io/savetag-support/"
UPDATED = "2026-08-19"
SHARED = ("n", "l", "tag", "nav", "lang", "foot")
FAQ_COUNT = 9
SEC_COUNT = 9
CHIP_COUNT = 6
TERMS_COUNT = 7
# page key -> output file. "s" support, "p" privacy, "t" terms of use.
PAGES = (("s", "index.html"), ("p", "privacy.html"), ("t", "terms.html"))


def expand(entry):
    """Fill the derived fields so each locale states its summary only once."""
    summary = entry["foot"]
    entry["s"]["meta"] = summary
    entry["p"]["meta"] = summary
    entry["p"]["lead"] = summary
    # the terms page describes itself, so its meta is its own lead
    entry["t"]["meta"] = entry["t"]["lead"]
    return entry


def load_terms(data):
    """Fold src/terms/*.json in: the third nav label and the "t" page block.

    Terms live in their own files so the support and privacy wording never has
    to be touched to add a legal page, but they merge into the same locale row
    the renderer already ships.
    """
    seen = set()
    for f in sorted((SRC / "terms").glob("part-*.json")):
        chunk = json.loads(f.read_text(encoding="utf-8"))
        for code, value in chunk.items():
            if code in seen:
                sys.exit(f"duplicate terms locale {code} in {f.name}")
            seen.add(code)
            if code not in data:
                sys.exit(f"terms for unknown locale {code} in {f.name}")
            data[code]["t"] = value["t"]
            data[code]["nav"] = list(data[code]["nav"]) + [value["nav"]]
    absent = [c for c in LOCALES if c not in seen]
    if absent:
        sys.exit(f"missing terms locales: {', '.join(absent)}")
    return data


def load_locales():
    data = {}
    for f in sorted((SRC / "locales").glob("part-*.json")):
        chunk = json.loads(f.read_text(encoding="utf-8"))
        for code, value in chunk.items():
            if code in data:
                sys.exit(f"duplicate locale {code} in {f.name}")
            data[code] = value
    load_terms(data)
    for code in list(data):
        expand(data[code])
    missing = [c for c in LOCALES if c not in data]
    extra = [c for c in data if c not in LOCALES]
    if missing:
        sys.exit(f"missing locales: {', '.join(missing)}")
    if extra:
        sys.exit(f"unknown locales: {', '.join(extra)}")
    return data


def slim(data, page):
    """Keep shared keys plus this page's block, in the shipped locale order."""
    out = {}
    for code in LOCALES:
        src = data[code]
        row = {k: src[k] for k in SHARED}
        row[page] = src[page]
        out[code] = row
    return out


def esc(text):
    return html.escape(text, quote=True)


def fallback(entry, page):
    """Static English markup so the page reads with JavaScript disabled."""
    block = entry[page]
    if page == "s":
        extra = "<ul class=\"chips\">" + "".join(
            f"<li>{esc(c)}</li>" for c in block["chips"]) + "</ul>"
        parts = [f'<h2 class="sect">{esc(block["faqT"])}<span class="rule"></span></h2>',
                 '<div class="faq">']
        for i, (q, a) in enumerate(block["faq"], 1):
            parts.append(
                f'<details class="q" open><summary><span class="n">{i}</span>'
                f'<span>{esc(q)}</span></summary><div class="a">{esc(a)}</div></details>')
        parts.append("</div>")
    else:
        extra = f'<p class="updated">{esc(block["upd"])} {UPDATED}</p>'
        parts = []
        if block.get("vow"):
            parts.append(
                f'<section class="card vow"><strong>{esc(block["vow"])}</strong></section>')
        for head, text in block["sec"]:
            parts.append(f'<section class="card policy"><h3>{esc(head)}</h3>'
                         f'<p>{esc(text)}</p></section>')
    parts.append(
        '<section class="card contact">'
        f'<h2>{esc(block["cT"])}</h2><p>{esc(block["cL"])}</p>'
        '<a class="btn" href="mailto:hourstag.app@gmail.com">'
        f'{esc(block["cB"])}</a>'
        '<a class="mail" href="mailto:hourstag.app@gmail.com">hourstag.app@gmail.com</a>'
        "</section>")
    return extra, "\n".join(parts)


def build():
    data = load_locales()
    css = (SRC / "style.css").read_text(encoding="utf-8")
    app = (SRC / "app.js").read_text(encoding="utf-8")
    tpl = (SRC / "page.tpl.html").read_text(encoding="utf-8")
    base = data["en-US"]

    for page, filename in PAGES:
        block = base[page]
        extra, body = fallback(base, page)
        payload = json.dumps(slim(data, page), ensure_ascii=False,
                             separators=(",", ":"))
        # </script> can never appear inside the JSON payload
        payload = payload.replace("</", "<\\/")
        out = (tpl
               .replace("__TITLE__", esc(block["title"]))
               .replace("__DESC__", esc(block["meta"]))
               .replace("__FILE__", "" if filename == "index.html" else filename)
               .replace("__PAGE__", page)
               .replace("__BADGE__", esc(block["eyebrow"]))
               .replace("__H1__", esc(block["h1"]))
               .replace("__LEAD__", esc(block["lead"]))
               .replace("__HERO_EXTRA__", extra)
               .replace("__FALLBACK__", body)
               .replace("__FOOT__", esc(base["foot"]))
               .replace("/*__CSS__*/", css)
               .replace("/*__APP__*/", app)
               .replace("/*__DATA__*/{}", payload))
        (ROOT / filename).write_text(out, encoding="utf-8")
        print(f"built {filename}  {len(out) / 1024:.0f} KB  "
              f"{len(LOCALES)} locales shipped, {len(PENDING)} pending")


if __name__ == "__main__":
    build()
