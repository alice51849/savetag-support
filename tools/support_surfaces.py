#!/usr/bin/env python3
"""Build and validate one repository's exact-50 public support surfaces."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "support_surfaces.json"
PROMOTION_SOURCE = ROOT / "source" / "support_promotions.json"
SURFACES = ("index", "support", "privacy")
FILES = {"index": "index.html", "support": "support.html", "privacy": "privacy.html"}
RTL = {"ar-SA", "he", "ur-PK"}
ENGLISH_LOGICAL = {"en-AU", "en-CA", "en-GB", "en-US"}
SAVE_TAG_APP_ID = "6802505528"
PROVIDER_TOKEN = "118326163"
OWN_CAMPAIGN_PREFIX = "iag_data"
FAMILY_CAMPAIGN = "sup_savetag"
FAMILY_APP_IDS = ("6785004775", "6794725568", "6794039979", "6780107485")
OFFICIAL = [
    "ar-SA", "bn-BD", "ca", "zh-Hans", "zh-Hant", "hr", "cs", "da",
    "nl-NL", "en-AU", "en-CA", "en-GB", "en-US", "fi", "fr-CA",
    "fr-FR", "de-DE", "el", "gu-IN", "he", "hi", "hu", "id", "it",
    "ja", "kn-IN", "ko", "ms", "ml-IN", "mr-IN", "no", "or-IN", "pl",
    "pt-BR", "pt-PT", "pa-IN", "ro", "ru", "sk", "sl-SI", "es-MX",
    "es-ES", "sv", "ta-IN", "te-IN", "th", "tr", "uk", "ur-PK", "vi",
]
SCRIPT_RANGES = {
    "ar-SA": r"[\u0600-\u06ff]", "he": r"[\u0590-\u05ff]",
    "ur-PK": r"[\u0600-\u06ff]", "bn-BD": r"[\u0980-\u09ff]",
    "gu-IN": r"[\u0a80-\u0aff]", "hi": r"[\u0900-\u097f]",
    "mr-IN": r"[\u0900-\u097f]", "kn-IN": r"[\u0c80-\u0cff]",
    "ml-IN": r"[\u0d00-\u0d7f]", "or-IN": r"[\u0b00-\u0b7f]",
    "pa-IN": r"[\u0a00-\u0a7f]", "ta-IN": r"[\u0b80-\u0bff]",
    "te-IN": r"[\u0c00-\u0c7f]", "el": r"[\u0370-\u03ff]",
    "ru": r"[\u0400-\u04ff]", "uk": r"[\u0400-\u04ff]",
    "zh-Hans": r"[\u3400-\u9fff]", "zh-Hant": r"[\u3400-\u9fff]",
    "ja": r"[\u3040-\u30ff\u3400-\u9fff]", "ko": r"[\uac00-\ud7af]",
    "th": r"[\u0e00-\u0e7f]",
}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
TAG_RE = re.compile(r"<[^>]+>")
RAW_KEY_RE = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b")
LINK_RE = re.compile(
    r"\s*<link\b(?=[^>]*\brel\s*=\s*[\"'](?:canonical|alternate)[\"'])[^>]*>",
    re.I,
)
META_RE = re.compile(
    r"\s*<meta\b(?=[^>]*(?:property|name)\s*=\s*[\"']"
    r"(?:og:url|og:locale|support-surface-authority)[\"'])[^>]*>",
    re.I,
)
SCHEMA_RE = re.compile(
    r"\s*<script\b[^>]*\bid\s*=\s*[\"']support-surface-schema[\"'][^>]*>"
    r".*?</script>",
    re.I | re.S,
)
APP_CTA_START = "<!-- ls-app-cta:start -->"
APP_CTA_END = "<!-- ls-app-cta:end -->"
APP_CTA_RE = re.compile(
    re.escape(APP_CTA_START) + r".*?" + re.escape(APP_CTA_END), re.S,
)
FAMILY_START = "<!-- ls-family:start -->"
FAMILY_END = "<!-- ls-family:end -->"
FAMILY_RE = re.compile(
    re.escape(FAMILY_START) + r".*?" + re.escape(FAMILY_END), re.S,
)
PROMOTION_RUNTIME_START = "<!-- ls-promotion-runtime:start -->"
PROMOTION_RUNTIME_END = "<!-- ls-promotion-runtime:end -->"
PROMOTION_RUNTIME_RE = re.compile(
    re.escape(PROMOTION_RUNTIME_START)
    + r".*?"
    + re.escape(PROMOTION_RUNTIME_END),
    re.S,
)


def load_source() -> dict:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    if data.get("schema") != "support-surface-source/v1":
        raise SystemExit("unsupported support surface source schema")
    if data.get("official_locales") != OFFICIAL:
        raise SystemExit("official locale list mismatch")
    if set(data.get("routes", {})) != set(OFFICIAL):
        raise SystemExit("route locale set mismatch")
    for locale in OFFICIAL:
        if set(data["routes"][locale]) != set(SURFACES):
            raise SystemExit(f"{locale}: route surface set mismatch")
    return data


def locale_campaign(locale: str) -> str:
    return f"{OWN_CAMPAIGN_PREFIX}_{locale.lower().replace('-', '_')}"


def direct_store_url(app_id: str, storefront: str, campaign: str) -> str:
    return (
        f"https://apps.apple.com/{storefront}/app/id{app_id}"
        f"?pt={PROVIDER_TOKEN}&ct={campaign}&mt=8"
    )


def validate_campaign_url(
    value: str,
    *,
    app_id: str,
    campaign: str,
    storefront: str | None,
) -> str | None:
    parts = urlsplit(value)
    expected_path = (
        f"/{storefront}/app/id{app_id}" if storefront else f"/app/id{app_id}"
    )
    if parts.scheme != "https" or parts.netloc != "apps.apple.com":
        return "must be a direct https://apps.apple.com URL"
    if parts.path != expected_path:
        return f"path {parts.path!r} != {expected_path!r}"
    if parse_qs(parts.query) != {
        "pt": [PROVIDER_TOKEN],
        "ct": [campaign],
        "mt": ["8"],
    }:
        return "campaign query mismatch"
    if parts.fragment:
        return "fragments are not allowed"
    return None


def load_promotions(data: dict) -> dict:
    promotions = json.loads(PROMOTION_SOURCE.read_text(encoding="utf-8"))
    problems = []
    if promotions.get("schema") != "support-promotion-source/v1":
        problems.append("unsupported promotion source schema")

    own = promotions.get("own_app") or {}
    if str(own.get("app_id")) != SAVE_TAG_APP_ID:
        problems.append(f"own App ID must be {SAVE_TAG_APP_ID}")
    if str(own.get("provider_token")) != PROVIDER_TOKEN:
        problems.append(f"provider token must be {PROVIDER_TOKEN}")
    if own.get("campaign_prefix") != OWN_CAMPAIGN_PREFIX:
        problems.append(f"own campaign prefix must be {OWN_CAMPAIGN_PREFIX}")
    english = own.get("english") or {}
    if set(english) != ENGLISH_LOGICAL:
        problems.append("English promotion locale set mismatch")

    index_targets = {
        target["locale"]: target
        for target in data.get("targets", [])
        if target.get("surface") == "index"
    }
    own_locales = {}
    for locale in OFFICIAL:
        if locale in ENGLISH_LOGICAL:
            entry = english.get(locale) or {}
            storefront = str(entry.get("storefront") or "")
            label = str(entry.get("label") or "")
            url = direct_store_url(
                SAVE_TAG_APP_ID, storefront, locale_campaign(locale)
            )
        else:
            target = index_targets.get(locale) or {}
            label = str(target.get("store_label") or "")
            url = str(target.get("store_url") or "")
            path_match = re.fullmatch(
                rf"/([a-z]{{2}})/app/id{SAVE_TAG_APP_ID}",
                urlsplit(url).path,
            )
            storefront = path_match.group(1) if path_match else ""
        if not storefront:
            problems.append(f"{locale}: missing App Store storefront")
        if not label or "app stor" not in label.lower():
            problems.append(f"{locale}: missing native App Store CTA label")
        issue = validate_campaign_url(
            url,
            app_id=SAVE_TAG_APP_ID,
            campaign=locale_campaign(locale),
            storefront=storefront or None,
        )
        if issue:
            problems.append(f"{locale}: own App URL {issue}")
        own_locales[locale] = {
            "url": url,
            "label": label,
            "storefront": storefront,
        }

    family = promotions.get("family") or {}
    if family.get("campaign") != FAMILY_CAMPAIGN:
        problems.append(f"family campaign must be {FAMILY_CAMPAIGN}")
    cards = family.get("cards") or []
    card_ids = tuple(str(card.get("app_id")) for card in cards)
    if card_ids != FAMILY_APP_IDS:
        problems.append("first-party family App ID set or order mismatch")
    for card in cards:
        app_id = str(card.get("app_id") or "")
        if card.get("first_party") is not True:
            problems.append(f"family App {app_id}: first_party must be true")
        if not str(card.get("name") or "").strip():
            problems.append(f"family App {app_id}: missing name")
        issue = validate_campaign_url(
            str(card.get("url") or ""),
            app_id=app_id,
            campaign=FAMILY_CAMPAIGN,
            storefront=None,
        )
        if issue:
            problems.append(f"family App {app_id}: URL {issue}")
        icon = urlsplit(str(card.get("icon") or ""))
        if icon.scheme != "https" or not (icon.hostname or "").endswith("mzstatic.com"):
            problems.append(f"family App {app_id}: icon is not an Apple CDN URL")

    guide = urlsplit(str(family.get("guide_url") or ""))
    if (
        guide.scheme != "https"
        or guide.netloc != "alice51849.github.io"
        or guide.path != "/ios-app-guide/"
        or parse_qs(guide.query)
        != {
            "utm_source": ["support_site"],
            "utm_medium": ["family_module"],
            "utm_campaign": [FAMILY_CAMPAIGN],
        }
    ):
        problems.append("family guide URL must be the first-party direct campaign URL")

    copy = family.get("copy") or {}
    if set(copy) != set(OFFICIAL):
        problems.append("family copy locale set mismatch")
    for locale in OFFICIAL:
        row = copy.get(locale) or {}
        if set(row) != {"heading", "note", "cta", "iap", "guide"}:
            problems.append(f"{locale}: family copy key mismatch")
            continue
        joined = " ".join(str(row[key]).strip() for key in sorted(row))
        if not joined or any(not str(row[key]).strip() for key in row):
            problems.append(f"{locale}: family copy is incomplete")
        if locale not in ENGLISH_LOGICAL:
            pattern = SCRIPT_RANGES.get(locale)
            if pattern and not re.search(pattern, joined):
                problems.append(f"{locale}: family copy lacks the expected script")

    if problems:
        raise SystemExit("\n".join(problems[:100]))
    promotions["_own_locales"] = own_locales
    return promotions


def path_url(base_url: str, relative: str) -> str:
    base = base_url.rstrip("/") + "/"
    if relative == "index.html":
        return base
    if relative.endswith("/index.html"):
        return base + relative[:-10]
    return base + relative


def route_url(data: dict, locale: str, surface: str) -> str:
    return path_url(data["base_url"], data["routes"][locale][surface])


def page_links(data: dict, surface: str) -> str:
    rows = [
        f'<link rel="alternate" hreflang="{locale}" '
        f'href="{html.escape(route_url(data, locale, surface), quote=True)}">'
        for locale in OFFICIAL
    ]
    rows.append(
        f'<link rel="alternate" hreflang="x-default" '
        f'href="{html.escape(route_url(data, "en-US", surface), quote=True)}">'
    )
    return "\n".join(rows)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_app_cta(promotions: dict, locale: str) -> str:
    own = promotions["_own_locales"][locale]
    return (
        f'{APP_CTA_START}<a class="button btn ls-app-store" '
        f'data-ls-app-store data-ls-locale="{esc(locale)}" '
        f'data-ls-app-id="{SAVE_TAG_APP_ID}" href="{esc(own["url"])}" '
        'rel="noopener" '
        'style="display:inline-flex;align-items:center;min-height:44px;'
        'padding:11px 20px;border-radius:14px;font-weight:720;'
        'text-decoration:none;color:#fff;'
        'background:linear-gradient(130deg,#FC67AA,#8980F7)">'
        f'{esc(own["label"])}</a>{APP_CTA_END}'
    )


def render_family_module(promotions: dict, locale: str) -> str:
    family = promotions["family"]
    copy = family["copy"][locale]
    rtl = locale in RTL
    direction = ' dir="rtl"' if rtl else ""
    align = "right" if rtl else "left"
    cards = []
    for card in family["cards"]:
        cards.append(
            f'<a href="{esc(card["url"])}" rel="noopener" '
            f'data-ls-family-app="{esc(card["app_id"])}" '
            'style="display:flex;align-items:center;gap:12px;padding:12px 14px;'
            'background:rgba(127,127,127,.10);'
            'background:color-mix(in srgb,currentColor 9%,transparent);'
            'border:1px solid rgba(127,127,127,.22);'
            'border-color:color-mix(in srgb,currentColor 20%,transparent);'
            'border-radius:16px;text-decoration:none;color:inherit;min-width:0;'
            f'text-align:{align}">'
            f'<img src="{esc(card["icon"])}" alt="" width="46" height="46" '
            'loading="lazy" style="border-radius:11px;flex:0 0 auto">'
            '<span style="min-width:0">'
            f'<strong style="display:block;font-size:14px;line-height:1.35">'
            f'{esc(card["name"])}</strong>'
            '<span data-ls-family-iap '
            'style="display:block;font-size:12px;line-height:1.4;opacity:.72">'
            f'{esc(copy["iap"])}</span>'
            '<span data-ls-family-cta '
            'style="display:block;font-size:12px;line-height:1.4;opacity:.72">'
            f'{esc(copy["cta"])}</span></span></a>'
        )
    return (
        f'{FAMILY_START}<section{direction} data-ls-family '
        f'data-ls-locale="{esc(locale)}" aria-label="{esc(copy["heading"])}" '
        'style="max-width:1060px;margin:34px auto 26px;padding:20px 22px;'
        'background:rgba(127,127,127,.08);'
        'background:color-mix(in srgb,currentColor 7%,transparent);'
        'border:1px solid rgba(127,127,127,.18);'
        'border-color:color-mix(in srgb,currentColor 16%,transparent);'
        'border-radius:20px;font-family:inherit;color:inherit;'
        f'text-align:{align}">'
        '<h2 data-ls-family-heading '
        'style="margin:0 0 14px;font-size:17px;color:inherit">'
        f'{esc(copy["heading"])}</h2>'
        '<div style="display:grid;grid-template-columns:repeat('
        'auto-fit,minmax(240px,1fr));gap:10px">'
        f'{"".join(cards)}</div>'
        '<p data-ls-family-note style="margin:10px 0 0;font-size:12px;opacity:.66">'
        f'{esc(copy["note"])}</p>'
        '<p style="margin:6px 0 0;font-size:12px;opacity:.66">'
        f'<a data-ls-family-guide href="{esc(family["guide_url"])}" rel="noopener" '
        'style="color:inherit;text-decoration:underline">'
        f'{esc(copy["guide"])}</a></p></section>{FAMILY_END}'
    )


def render_promotion_runtime(promotions: dict) -> str:
    payload = {
        locale: {
            "url": promotions["_own_locales"][locale]["url"],
            "label": promotions["_own_locales"][locale]["label"],
            "family": promotions["family"]["copy"][locale],
        }
        for locale in OFFICIAL
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    return (
        f'{PROMOTION_RUNTIME_START}<script id="ls-promotion-routes" '
        f'type="application/json">{encoded}</script>\n'
        """<script id="ls-promotion-router">
(function () {
  "use strict";
  var node = document.getElementById("ls-promotion-routes");
  if (!node) return;
  var routes = JSON.parse(node.textContent);
  var order = Object.keys(routes);
  var englishOnly = !document.getElementById("lang");
  function normalise(value) {
    if (!value) return null;
    var tag = String(value).replace("_", "-").toLowerCase();
    for (var i = 0; i < order.length; i += 1) {
      if (order[i].toLowerCase() === tag) return order[i];
    }
    var base = tag.split("-")[0];
    if (base === "en") {
      if (/^(en-)?au$/.test(tag)) return "en-AU";
      if (/^(en-)?ca$/.test(tag)) return "en-CA";
      if (/^(en-)?(gb|uk)$/.test(tag)) return "en-GB";
      return "en-US";
    }
    for (var j = 0; j < order.length; j += 1) {
      if (order[j].toLowerCase().split("-")[0] === base) return order[j];
    }
    return null;
  }
  function parameter() {
    var match = /[?&]lang=([^&#]+)/.exec(location.search);
    return match ? decodeURIComponent(match[1]) : null;
  }
  function stored() {
    try { return localStorage.getItem("savetag.lang"); }
    catch (error) { return null; }
  }
  function pick() {
    var detected = navigator.languages || [navigator.language];
    var values = [parameter(), stored()];
    values = englishOnly
      ? values.concat(detected, [document.documentElement.lang])
      : values.concat([document.documentElement.lang], detected);
    for (var i = 0; i < values.length; i += 1) {
      var code = normalise(values[i]);
      if (code && (!englishOnly || code.slice(0, 3) === "en-")) return code;
    }
    return "en-US";
  }
  function apply() {
    var code = pick();
    var row = routes[code] || routes["en-US"];
    document.querySelectorAll("[data-ls-app-store]").forEach(function (link) {
      link.href = row.url;
      link.textContent = row.label;
      link.setAttribute("data-ls-locale", code);
    });
    document.querySelectorAll("[data-ls-family]").forEach(function (section) {
      section.dir = /^(ar-SA|he|ur-PK)$/.test(code) ? "rtl" : "ltr";
      section.setAttribute("data-ls-locale", code);
      section.setAttribute("aria-label", row.family.heading);
    });
    document.querySelectorAll("[data-ls-family-heading]").forEach(function (item) {
      item.textContent = row.family.heading;
    });
    document.querySelectorAll("[data-ls-family-note]").forEach(function (item) {
      item.textContent = row.family.note;
    });
    document.querySelectorAll("[data-ls-family-cta]").forEach(function (item) {
      item.textContent = row.family.cta;
    });
    document.querySelectorAll("[data-ls-family-iap]").forEach(function (item) {
      item.textContent = row.family.iap;
    });
    document.querySelectorAll("[data-ls-family-guide]").forEach(function (item) {
      item.textContent = row.family.guide;
    });
  }
  document.addEventListener("change", function (event) {
    if (event.target && event.target.id === "lang") setTimeout(apply, 0);
  }, true);
  new MutationObserver(apply).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["lang", "dir"]
  });
  apply();
})();
</script>"""
        f"{PROMOTION_RUNTIME_END}"
    )


def render(data: dict, target: dict) -> str:
    locale = target["locale"]
    surface = target["surface"]
    canonical = route_url(data, locale, surface)
    nav = []
    for key, label in zip(SURFACES, target["nav"], strict=True):
        current = ' aria-current="page"' if key == surface else ""
        nav.append(f'<a href="{esc(route_url(data, locale, key))}"{current}>{esc(label)}</a>')
    language_links = "".join(
        f'<a lang="{code}" hreflang="{code}" href="{esc(route_url(data, code, surface))}"'
        f'{" aria-current=\"true\"" if code == locale else ""}>'
        f'{esc(data["language_names"][code])}</a>'
        for code in OFFICIAL
    )
    sections = "".join(
        f'<section class="card"><h2>{esc(item["heading"])}</h2>'
        f'<p>{esc(item["body"])}</p></section>'
        for item in target.get("sections", [])
    )
    faq_items = target.get("faqs", [])
    faqs = ""
    if faq_items:
        faq_rows = "".join(
            f'<details><summary>{esc(question)}</summary><p>{esc(answer)}</p></details>'
            for question, answer in faq_items
        )
        faqs = (
            f'<section class="card wide"><h2>{esc(target["faq_heading"])}</h2>'
            f'{faq_rows}</section>'
        )
    parent_note = (
        f'<aside class="parent-note">{esc(target["parent_note"])}</aside>'
        if target.get("parent_note") else ""
    )
    secondary = (
        f'<a class="quiet-button" href="{esc(route_url(data, locale, "support"))}">'
        f'{esc(target["support_label"])}</a>'
        if surface == "index" else ""
    )
    icon = ""
    if data.get("icon_url"):
        icon = f'<img src="{esc(data["icon_url"])}" width="42" height="42" alt="">'
    contact = ""
    if surface in {"support", "privacy"}:
        contact = (
            f'<section class="card wide contact"><h2>{esc(target["contact_heading"])}</h2>'
            f'<p>{esc(target["contact_body"])}</p>'
            f'<a class="button" href="mailto:{esc(data["email"])}">'
            f'{esc(target["contact_button"])}</a>'
            f'<a class="email" href="mailto:{esc(data["email"])}">{esc(data["email"])}</a>'
            f'</section>'
        )
    graph = [{
        "@type": "WebPage",
        "url": canonical,
        "name": target["title"],
        "inLanguage": locale,
        "isPartOf": {"@type": "WebSite", "url": data["base_url"]},
    }]
    if faq_items:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faq_items
            ],
        })
    schema = json.dumps(
        {"@context": "https://schema.org", "@graph": graph},
        ensure_ascii=False, separators=(",", ":"),
    ).replace("</", "<\\/")
    theme = data["theme"]
    return f"""<!doctype html>
<html lang="{esc(locale)}" dir="{"rtl" if locale in RTL else "ltr"}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="support-surface-generated" content="support-surface-source/v1">
<meta name="support-surface-authority" content="{esc(data["authority_digest"])}">
<title>{esc(target["title"])}</title>
<meta name="description" content="{esc(target["description"]) }">
<link rel="canonical" href="{esc(canonical)}">
{page_links(data, surface)}
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(target["title"])}">
<meta property="og:description" content="{esc(target["description"])}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:locale" content="{esc(locale.replace("-", "_"))}">
<script id="support-surface-schema" type="application/ld+json">{schema}</script>
<style>
:root{{--ink:{theme["ink"]};--muted:{theme["muted"]};--a1:{theme["a1"]};--a2:{theme["a2"]};--line:color-mix(in srgb,var(--a1) 22%,transparent)}}
*{{box-sizing:border-box}}html{{background:{theme["background"]}}}
body{{margin:0;min-height:100vh;color:var(--ink);font:16px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans","Noto Sans Arabic","Noto Sans Devanagari","Noto Sans Bengali","Noto Sans Tamil","Noto Sans Telugu","Noto Sans Kannada","Noto Sans Malayalam","Noto Sans Gujarati","Noto Sans Gurmukhi","Noto Sans Thai",sans-serif;background:radial-gradient(circle at 8% 0%,color-mix(in srgb,var(--a1) 16%,transparent),transparent 32rem),radial-gradient(circle at 92% 4%,color-mix(in srgb,var(--a2) 14%,transparent),transparent 30rem)}}
a{{color:var(--a1);text-decoration:none}}a:focus-visible,summary:focus-visible{{outline:3px solid color-mix(in srgb,var(--a1) 45%,transparent);outline-offset:4px}}
.shell{{width:min(1040px,calc(100% - 34px));margin:auto}}header{{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:22px 0;flex-wrap:wrap}}
.brand{{display:flex;align-items:center;gap:11px;color:var(--ink);font-weight:750}}.brand img{{border-radius:12px}}
nav{{display:flex;gap:5px;flex-wrap:wrap}}nav a{{min-height:44px;padding:10px 13px;border-radius:13px;color:var(--muted);font-weight:650}}nav a[aria-current]{{background:color-mix(in srgb,var(--a1) 12%,transparent);color:var(--a1)}}
.language{{position:relative}}.language summary{{min-height:44px;padding:10px 13px;border:1px solid var(--line);border-radius:13px;cursor:pointer;list-style:none}}.language summary::-webkit-details-marker{{display:none}}
.language-list{{position:absolute;z-index:5;inset-inline-end:0;top:52px;width:min(600px,calc(100vw - 24px));max-height:66vh;overflow:auto;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;padding:12px;border:1px solid var(--line);border-radius:18px;background:{theme["panel"]};box-shadow:0 20px 60px color-mix(in srgb,var(--a1) 18%,transparent)}}.language-list a{{padding:8px 10px;border-radius:10px;color:var(--muted)}}.language-list a[aria-current]{{background:color-mix(in srgb,var(--a1) 12%,transparent);color:var(--a1)}}
main{{padding:18px 0 8px}}.hero{{padding:20px 0 30px}}.eyebrow{{margin:0;color:var(--a1);font-size:13px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}}h1{{margin:12px 0 8px;font-size:clamp(31px,6vw,54px);line-height:1.12;font-weight:720;letter-spacing:-.025em}}.lead{{max-width:70ch;margin:0;color:var(--muted);font-size:18px}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}}.button,.quiet-button{{display:inline-flex;align-items:center;min-height:44px;padding:11px 20px;border-radius:14px;font-weight:720}}.button{{color:white;background:linear-gradient(130deg,var(--a1),var(--a2))}}.quiet-button{{border:1px solid var(--line);color:var(--muted);background:{theme["panel"]}}}
.parent-note{{margin-top:17px;padding:13px 16px;border-inline-start:4px solid var(--a1);border-radius:10px;background:color-mix(in srgb,var(--a1) 9%,transparent);color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:15px}}.card{{padding:21px 23px;border:1px solid var(--line);border-radius:19px;background:{theme["panel"]};box-shadow:0 18px 44px color-mix(in srgb,var(--a1) 10%,transparent)}}.wide{{grid-column:1/-1}}.card h2{{margin:0 0 8px;font-size:20px}}.card p{{margin:0;color:var(--muted)}}details{{padding:13px 0;border-top:1px solid var(--line)}}details:first-of-type{{border-top:0}}summary{{cursor:pointer;font-weight:690}}details p{{margin-top:8px!important}}.contact{{margin-top:15px}}.email{{display:inline-flex;margin:12px;color:var(--muted)}}
footer{{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-top:28px;padding:25px 0 38px;border-top:1px solid var(--line);color:var(--muted);font-size:14px}}
@media(max-width:720px){{.language-list{{position:fixed;inset:76px 12px auto;grid-template-columns:repeat(2,minmax(0,1fr))}}}}
</style>
</head>
<body>
<div class="shell">
<header><a class="brand" href="{esc(route_url(data, locale, "index"))}">{icon}<span>{esc(target["app_name"])}</span></a><nav aria-label="{esc(target["nav_label"])}">{''.join(nav)}</nav><details class="language"><summary>{esc(target["language_label"])}</summary><div class="language-list">{language_links}</div></details></header>
<main>
<section class="hero"><p class="eyebrow">{esc(target["eyebrow"])}</p><h1>{esc(target["heading"])}</h1><p class="lead">{esc(target["lead"])}</p>{parent_note}<div class="actions">{secondary}</div></section>
<div class="grid">{sections}{faqs}{contact}</div>
</main>
<footer><span>© 2026 {esc(target["app_name"])}</span><span>{esc(target["footer_note"])}</span></footer>
</div>
</body>
</html>
"""


def set_html_identity(text: str, locale: str) -> str:
    match = re.search(r"<html\b([^>]*)>", text, re.I)
    if not match:
        raise ValueError("missing html element")
    attrs = match.group(1)
    attrs = re.sub(r"\s+(?:lang|dir)\s*=\s*[\"'][^\"']*[\"']", "", attrs, flags=re.I)
    replacement = f'<html{attrs} lang="{locale}" dir="{"rtl" if locale in RTL else "ltr"}">'
    return text[:match.start()] + replacement + text[match.end():]


def strip_standalone_block(text: str, pattern: re.Pattern[str]) -> str:
    while match := pattern.search(text):
        text = text[:match.start()].rstrip() + "\n" + text[match.end():].lstrip()
    return text


def route_locales(data: dict, relative: str, surface: str) -> list[str]:
    return [
        locale
        for locale in OFFICIAL
        if data["routes"][locale][surface] == relative
    ]


def inject_promotions(
    text: str,
    data: dict,
    promotions: dict,
    relative: str,
    locale: str,
    surface: str,
) -> str:
    text = APP_CTA_RE.sub("", text)
    text = strip_standalone_block(text, FAMILY_RE)
    text = strip_standalone_block(text, PROMOTION_RUNTIME_RE)
    cta = render_app_cta(promotions, locale)

    hero = re.search(
        r'<section\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bhero\b[^"\']*["\'])'
        r"[^>]*>",
        text,
        re.I,
    )
    if not hero:
        raise ValueError(f"{relative}: missing hero for App Store CTA")
    hero_close = re.search(r"</section\s*>", text[hero.end():], re.I)
    if not hero_close:
        raise ValueError(f"{relative}: hero is not closed")
    hero_end = hero.end() + hero_close.start()
    actions = re.search(
        r'<div\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bactions\b[^"\']*["\'])'
        r"[^>]*>",
        text[hero.end():hero_end],
        re.I,
    )
    if actions:
        insertion = hero.end() + actions.end()
        text = text[:insertion] + cta + text[insertion:]
    else:
        wrapper = (
            '<div class="actions" '
            'style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px">'
            f"{cta}</div>"
        )
        text = text[:hero_end] + wrapper + text[hero_end:]

    footer_matches = list(re.finditer(r"<footer\b", text, re.I))
    if not footer_matches:
        raise ValueError(f"{relative}: missing footer for family module")
    footer = footer_matches[-1].start()
    text = (
        text[:footer].rstrip()
        + "\n\n"
        + render_family_module(promotions, locale)
        + "\n"
        + text[footer:].lstrip()
    )

    logical_locales = route_locales(data, relative, surface)
    if len(logical_locales) > 1:
        if set(logical_locales) != ENGLISH_LOGICAL:
            raise ValueError(
                f"{relative}: unsupported shared locale set {logical_locales!r}"
            )
        body_matches = list(re.finditer(r"</body\s*>", text, re.I))
        if not body_matches:
            raise ValueError(f"{relative}: missing body close for promotion runtime")
        body_close = body_matches[-1].start()
        text = (
            text[:body_close].rstrip()
            + "\n"
            + render_promotion_runtime(promotions)
            + "\n"
            + text[body_close:].lstrip()
        )
    return text


def normalize_page(
    data: dict,
    promotions: dict,
    relative: str,
    locale: str,
    surface: str,
) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    text = set_html_identity(text, locale)
    canonical = path_url(data["base_url"], relative)
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    page_name = TAG_RE.sub(" ", title.group(1)).strip() if title else data["site"]
    schema = json.dumps({
        "@context": "https://schema.org", "@type": "WebPage", "url": canonical,
        "name": html.unescape(page_name), "inLanguage": locale,
    }, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    block = (
        f'\n<meta name="support-surface-authority" content="{esc(data["authority_digest"])}">'
        f'\n<link rel="canonical" href="{esc(canonical)}">\n{page_links(data, surface)}'
        f'\n<meta property="og:url" content="{esc(canonical)}">'
        f'\n<meta property="og:locale" content="{esc(locale.replace("-", "_"))}">'
        f'\n<script id="support-surface-schema" type="application/ld+json">{schema}</script>\n'
    )
    text = re.sub(r"<!--\s*ls-i18n:(?:start|end)\s*-->", "", text, flags=re.I)
    text = LINK_RE.sub("", text)
    text = META_RE.sub("", text)
    text = SCHEMA_RE.sub("", text)
    if "</head>" not in text.lower():
        raise ValueError(f"{relative}: missing head close")
    text = re.sub(r"</head>", block + "</head>", text, count=1, flags=re.I)
    text = inject_promotions(
        text, data, promotions, relative, locale, surface
    )
    path.write_text(text, encoding="utf-8")


def unique_routes(data: dict) -> dict[str, tuple[str, str]]:
    users: dict[str, list[tuple[str, str]]] = {}
    for locale in OFFICIAL:
        for surface in SURFACES:
            users.setdefault(data["routes"][locale][surface], []).append((locale, surface))
    result = {}
    for path, values in users.items():
        locales = [item[0] for item in values]
        locale = "en-US" if "en-US" in locales else values[0][0]
        result[path] = (locale, values[0][1])
    return result


def merge_sitemap(data: dict) -> None:
    path = ROOT / "sitemap.xml"
    existing = set()
    if path.exists():
        existing.update(html.unescape(x) for x in re.findall(r"<loc>(.*?)</loc>", path.read_text(encoding="utf-8"), re.I | re.S))
    existing.update(path_url(data["base_url"], relative) for relative in unique_routes(data))
    rows = "\n".join(f"  <url><loc>{esc(url)}</loc></url>" for url in sorted(existing))
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{rows}\n</urlset>\n",
        encoding="utf-8",
    )


def build(data: dict, promotions: dict) -> str:
    for target in data.get("targets", []):
        destination = ROOT / target["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render(data, target), encoding="utf-8")
    for relative, (locale, surface) in unique_routes(data).items():
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"missing required output: {relative}")
        normalize_page(data, promotions, relative, locale, surface)
    merge_sitemap(data)
    return content_digest(data)


def visible_text(text: str) -> str:
    text = re.sub(r"<(?:script|style)\b.*?</(?:script|style)>", " ", text, flags=re.I | re.S)
    return " ".join(html.unescape(TAG_RE.sub(" ", text)).split())


def attr_values(text: str, tag: str, attr: str, required: tuple[str, str] | None = None) -> list[str]:
    out = []
    for match in re.finditer(fr"<{tag}\b([^>]*)>", text, re.I):
        attrs = match.group(1)
        if required:
            req = re.search(fr"\b{required[0]}\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
            if not req or req.group(1).lower() != required[1].lower():
                continue
        value = re.search(fr"\b{attr}\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
        if value:
            out.append(html.unescape(value.group(1)))
    return out


def resolve_local(data: dict, current: str, href: str) -> Path | None:
    if not href or href.startswith(("#", "mailto:", "tel:")):
        return None
    parts = urlsplit(href)
    if parts.scheme:
        base = urlsplit(data["base_url"])
        if (parts.scheme, parts.netloc) != (base.scheme, base.netloc):
            return None
        prefix = base.path.rstrip("/") + "/"
        if not parts.path.startswith(prefix):
            return None
        rel = unquote(parts.path[len(prefix):])
    elif href.startswith("/"):
        prefix = urlsplit(data["base_url"]).path.rstrip("/") + "/"
        if not href.startswith(prefix):
            return None
        rel = unquote(href[len(prefix):].split("?", 1)[0].split("#", 1)[0])
    else:
        rel = str((Path(current).parent / unquote(parts.path)).as_posix())
    candidate = ROOT / rel
    if not candidate.suffix:
        candidate = candidate / "index.html"
    return candidate


def promotion_errors(
    data: dict,
    promotions: dict,
    relative: str,
    locale: str,
    surface: str,
    text: str,
) -> list[str]:
    errors = []
    cta_blocks = APP_CTA_RE.findall(text)
    if len(cta_blocks) != 1:
        errors.append(f"{relative}: expected exactly one generated App Store CTA")
    else:
        block = cta_blocks[0]
        hrefs = attr_values(block, "a", "href")
        expected = promotions["_own_locales"][locale]
        if hrefs != [expected["url"]]:
            errors.append(f"{relative}: own App Store CTA URL mismatch")
        if expected["label"] not in visible_text(block):
            errors.append(f"{relative}: own App Store CTA label mismatch")
        ids = attr_values(block, "a", "data-ls-app-id")
        if ids != [SAVE_TAG_APP_ID]:
            errors.append(f"{relative}: own App Store CTA ID mismatch")

    family_blocks = FAMILY_RE.findall(text)
    if len(family_blocks) != 1:
        errors.append(f"{relative}: expected exactly one ls-family module")
    else:
        block = family_blocks[0]
        family = promotions["family"]
        copy = family["copy"][locale]
        expected_hrefs = [card["url"] for card in family["cards"]]
        expected_hrefs.append(family["guide_url"])
        if attr_values(block, "a", "href") != expected_hrefs:
            errors.append(f"{relative}: family direct-link set mismatch")
        if attr_values(block, "a", "data-ls-family-app") != list(FAMILY_APP_IDS):
            errors.append(f"{relative}: family first-party App set mismatch")
        plain = visible_text(block)
        for key in ("heading", "note", "cta", "iap", "guide"):
            if copy[key] not in plain:
                errors.append(f"{relative}: native family {key} copy mismatch")
        if SAVE_TAG_APP_ID in block:
            errors.append(f"{relative}: family module recommends SaveTag to itself")

    logical_locales = route_locales(data, relative, surface)
    runtime = re.search(
        r'<script\b(?=[^>]*\bid=["\']ls-promotion-routes["\'])'
        r'[^>]*>(.*?)</script>',
        text,
        re.I | re.S,
    )
    if len(logical_locales) > 1:
        if set(logical_locales) != ENGLISH_LOGICAL:
            errors.append(f"{relative}: invalid shared promotion locale set")
        try:
            if not runtime:
                raise ValueError("missing")
            payload = json.loads(runtime.group(1))
        except (ValueError, json.JSONDecodeError):
            errors.append(f"{relative}: invalid promotion runtime payload")
        else:
            if set(payload) != set(OFFICIAL):
                errors.append(f"{relative}: promotion runtime locale set mismatch")
            for code in OFFICIAL:
                row = payload.get(code) or {}
                expected = promotions["_own_locales"][code]
                if row.get("url") != expected["url"]:
                    errors.append(f"{relative}: runtime {code} URL mismatch")
                    break
                if row.get("label") != expected["label"]:
                    errors.append(f"{relative}: runtime {code} CTA mismatch")
                    break
                if row.get("family") != promotions["family"]["copy"][code]:
                    errors.append(f"{relative}: runtime {code} family copy mismatch")
                    break
    elif runtime or PROMOTION_RUNTIME_START in text or PROMOTION_RUNTIME_END in text:
        errors.append(f"{relative}: unexpected promotion runtime payload")
    return errors


def javascript_errors(data: dict, route_set: dict[str, tuple[str, str]]) -> tuple[list[str], dict]:
    errors = []
    node = shutil.which("node")
    if not node:
        return ["JavaScript syntax gate: node is unavailable"], {
            "inline_checked": 0,
            "external_checked": 0,
        }
    scripts: dict[str, tuple[str, str]] = {}
    inline = 0
    external = 0
    for relative in route_set:
        text = (ROOT / relative).read_text(encoding="utf-8")
        for match in re.finditer(r"<script\b([^>]*)>(.*?)</script>", text, re.I | re.S):
            attrs, body = match.groups()
            kind = re.search(r'\btype\s*=\s*["\']([^"\']+)["\']', attrs, re.I)
            if kind and kind.group(1).lower() in {
                "application/json",
                "application/ld+json",
            }:
                continue
            source = re.search(r'\bsrc\s*=\s*["\']([^"\']+)["\']', attrs, re.I)
            if source:
                path = resolve_local(data, relative, html.unescape(source.group(1)))
                if path is None or not path.is_file():
                    errors.append(f"{relative}: external or missing JavaScript source")
                    continue
                body = path.read_text(encoding="utf-8")
                label = str(path.relative_to(ROOT))
                external += 1
            else:
                if not body.strip():
                    continue
                label = relative
                inline += 1
            key = hashlib.sha256(body.encode()).hexdigest()
            scripts.setdefault(key, (label, body))
    for label, body in scripts.values():
        try:
            result = subprocess.run(
                [node, "--check"],
                input=body,
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{label}: JavaScript syntax gate failed ({exc})")
            continue
        if result.returncode:
            detail = (result.stderr or result.stdout).strip().splitlines()
            errors.append(
                f"{label}: invalid JavaScript"
                + (f" ({detail[-1]})" if detail else "")
            )
    return errors, {
        "inline_checked": inline,
        "external_checked": external,
        "unique_checked": len(scripts),
    }


def check(data: dict, promotions: dict) -> dict:
    errors = []
    allowed_email = data["email"].lower()
    route_set = unique_routes(data)
    target_paths = {target["path"]: target for target in data.get("targets", [])}
    expected_hreflang = set(OFFICIAL) | {"x-default"}
    for relative, (locale, surface) in route_set.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"{relative}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        html_lang = attr_values(text, "html", "lang")
        html_dir = attr_values(text, "html", "dir")
        if html_lang != [locale]:
            errors.append(f"{relative}: html lang {html_lang!r} != {locale}")
        expected_dir = "rtl" if locale in RTL else "ltr"
        if html_dir != [expected_dir]:
            errors.append(f"{relative}: html dir {html_dir!r} != {expected_dir}")
        canonicals = attr_values(text, "link", "href", ("rel", "canonical"))
        expected_canonical = path_url(data["base_url"], relative)
        if canonicals != [expected_canonical]:
            errors.append(f"{relative}: canonical mismatch")
        alternates = {}
        for match in re.finditer(r"<link\b([^>]*)>", text, re.I):
            attrs = match.group(1)
            rel = re.search(r"\brel\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
            if not rel or rel.group(1).lower() != "alternate":
                continue
            lang = re.search(r"\bhreflang\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
            href = re.search(r"\bhref\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
            if lang and href:
                alternates[lang.group(1)] = html.unescape(href.group(1))
        if set(alternates) != expected_hreflang:
            errors.append(f"{relative}: hreflang set mismatch")
        else:
            for code in OFFICIAL:
                if alternates[code] != route_url(data, code, surface):
                    errors.append(f"{relative}: hreflang {code} URL mismatch")
                    break
        schema_match = re.search(
            r'<script\b[^>]*id=["\']support-surface-schema["\'][^>]*>(.*?)</script>',
            text, re.I | re.S,
        )
        try:
            if not schema_match:
                raise ValueError("missing")
            json.loads(schema_match.group(1))
        except (ValueError, json.JSONDecodeError):
            errors.append(f"{relative}: invalid support schema")
        authority = attr_values(text, "meta", "content", ("name", "support-surface-authority"))
        if authority != [data["authority_digest"]]:
            errors.append(f"{relative}: authority digest mismatch")
        emails = {item.lower() for item in EMAIL_RE.findall(text)}
        if emails - {allowed_email}:
            errors.append(f"{relative}: unapproved public email")
        plain = visible_text(text)
        if surface == "support":
            if len(plain) < 80 or allowed_email not in plain.lower():
                errors.append(f"{relative}: support equivalence gate failed")
        if surface == "privacy" and len(re.findall(r"<h[23]\b", text, re.I)) < 4:
            errors.append(f"{relative}: privacy content too thin")
        for href in attr_values(text, "a", "href"):
            if href.lower().startswith("mailto:") and allowed_email not in href.lower():
                errors.append(f"{relative}: wrong mailto")
                continue
            local = resolve_local(data, relative, href)
            if local is not None and not local.is_file():
                errors.append(f"{relative}: broken local link {href}")
        target = target_paths.get(relative)
        if target:
            if 'name="support-surface-generated"' not in text:
                errors.append(f"{relative}: generated marker missing")
            if RAW_KEY_RE.search(plain) or "{{" in plain or "}}" in plain:
                errors.append(f"{relative}: raw key or placeholder visible")
            if locale not in {"en-US", "en-AU", "en-CA", "en-GB"}:
                pattern = SCRIPT_RANGES.get(locale)
                if pattern and not re.search(pattern, plain):
                    errors.append(f"{relative}: expected script is absent")
        errors.extend(
            promotion_errors(
                data, promotions, relative, locale, surface, text
            )
        )
    for surface in SURFACES:
        expected = FILES[surface]
        for locale in ENGLISH_LOGICAL:
            if data["routes"][locale][surface] != expected:
                errors.append(
                    f"{locale}/{surface}: root English logical route mismatch"
                )
    js_errors, javascript = javascript_errors(data, route_set)
    errors.extend(js_errors)
    if errors:
        raise SystemExit("\n".join(errors[:100]))
    return {
        "site": data["site"],
        "required_cells": len(OFFICIAL) * len(SURFACES),
        "unique_files": len(route_set),
        "targets": len(data.get("targets", [])),
        "digest": content_digest(data),
        "english_logical_routes": len(ENGLISH_LOGICAL) * len(SURFACES),
        "promotion_pages": len(route_set),
        "javascript": javascript,
        "status": "PASS",
    }


def content_digest(data: dict) -> str:
    digest = hashlib.sha256()
    for relative in sorted(unique_routes(data)):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update((ROOT / relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check", "digest"))
    args = parser.parse_args()
    data = load_source()
    promotions = load_promotions(data)
    if args.command == "build":
        print(json.dumps(
            {"site": data["site"], "digest": build(data, promotions)},
            sort_keys=True,
        ))
    elif args.command == "check":
        print(json.dumps(check(data, promotions), sort_keys=True))
    else:
        print(content_digest(data))


if __name__ == "__main__":
    main()
