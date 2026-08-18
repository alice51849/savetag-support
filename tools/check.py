#!/usr/bin/env python3
"""Validate the SaveTag support site. Prints PASS or exits non-zero.

Checks:
 1. every one of the 50 shipped locales has complete support, privacy and terms
    content, with the same number of chips, FAQ entries, policy sections and
    terms sections as English,
 2. every FAQ / policy entry is a non-empty [heading, body] pair, and no locale
    other than the English variants is a copy of the English text,
 3. all three built pages embed every shipped locale in the switcher payload,
 4. the only public contact address anywhere in the repo is
    hourstag.app@gmail.com (the private mail domains are banned outright),
 5. the website itself references no external host and no tracker,
 6. the honesty contract: the site claims only what the app does — on-device
    NaturalLanguage tagging (never cloud or generative AI), a 5-save free tier,
    a one-time purchase that is never a subscription, on-device link-preview
    fetching disclosed rather than denied,
 7. the terms of use hold the same promise in every language: each locale states
    in its own words that Pro is not a subscription, and no locale quotes a
    price, so the page can never contradict what the App Store charges.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build import (  # noqa: E402
    CHIP_COUNT,
    FAQ_COUNT,
    LOCALES,
    SEC_COUNT,
    SHARED,
    TERMS_COUNT,
    load_locales,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_ROOT = ROOT.parent / "48_SaveTag"
MAIL = "hourstag.app@gmail.com"
# built from parts so this file never contains the banned literal itself
BANNED = ("@" + "hotmail.com", "@" + "outlook.com")
PAGES = ("index.html", "privacy.html", "terms.html")
ENGLISH = {"en-US", "en-GB", "en-AU", "en-CA"}
# The purchase section of the terms must deny a subscription in the locale's own
# words: (the word for "subscription", the negation that has to sit beside it).
# Written out per locale so a translation can never quietly drop the denial.
NOSUB = {
    "en-US": ("subscription", "never"), "en-GB": ("subscription", "never"),
    "en-AU": ("subscription", "never"), "en-CA": ("subscription", "never"),
    "zh-Hant": ("訂閱", "絕不是"), "zh-Hans": ("订阅", "绝不是"),
    "ja": ("サブスクリプション", "ではありません"), "ko": ("구독", "아니"),
    "de-DE": ("Abonnement", "kein"), "fr-FR": ("abonnement", "jamais"),
    "fr-CA": ("abonnement", "jamais"), "es-ES": ("suscripción", "nunca"),
    "es-MX": ("suscripción", "nunca"), "it": ("abbonamento", "non è mai"),
    "pt-BR": ("assinatura", "nunca"), "pt-PT": ("subscrição", "nunca"),
    "nl-NL": ("abonnement", "nooit"), "sv": ("prenumeration", "aldrig"),
    "da": ("abonnement", "aldrig"), "fi": ("tilaus", "ei ole koskaan"),
    "no": ("abonnement", "aldri"), "ru": ("подписка", "никогда"),
    "pl": ("subskrypcja", "nigdy"), "tr": ("abonelik", "asla"),
    "cs": ("předplatné", "nikdy"), "sk": ("predplatné", "nikdy"),
    "hr": ("pretplata", "nikada"), "hu": ("előfizetés", "soha"),
    "ro": ("abonament", "niciodată"), "uk": ("підписка", "ніколи"),
    "el": ("συνδρομή", "ποτέ"), "ca": ("subscripció", "mai"),
    "sl-SI": ("naročnin", "nikoli"), "ar-SA": ("اشتراك", "ليست"),
    "he": ("מנוי", "לעולם לא"), "hi": ("सदस्यता", "कभी"),
    "th": ("สมัครสมาชิก", "ไม่ใช่"), "vi": ("đăng ký", "không bao giờ"),
    "id": ("langganan", "tidak pernah"), "ms": ("langganan", "bukan"),
    "ur-PK": ("سبسکرپشن", "کبھی"), "bn-BD": ("সাবস্ক্রিপশন", "কখনও"),
    "gu-IN": ("સબ્સ્ક્રિપ્શન", "ક્યારેય"), "kn-IN": ("ಚಂದಾದಾರಿಕೆ", "ಎಂದಿಗೂ"),
    "ml-IN": ("സബ്‌സ്‌ക്രിപ്ഷൻ", "ഒരിക്കലും"), "mr-IN": ("सदस्यता", "कधीही"),
    "or-IN": ("ସବସ୍କ୍ରିପସନ", "କେବେ ବି"), "pa-IN": ("ਸਬਸਕ੍ਰਿਪਸ਼ਨ", "ਕਦੇ ਵੀ"),
    "ta-IN": ("சந்தா", "ஒருபோதும்"), "te-IN": ("సబ్‌స్క్రిప్షన్", "ఎప్పుడూ"),
}
# A price belongs to the App Store, never to this page.
MONEY = ("$", "€", "£", "¥", "₩", "₹", "₺", "₫", "₪", "฿", "NT")
FAIL = []


def bad(msg):
    FAIL.append(msg)


def check_content():
    data = load_locales()
    en = data["en-US"]
    for code in LOCALES:
        t = data[code]
        for key in SHARED:
            if not t.get(key):
                bad(f"{code}: missing shared key {key}")
        if len(t.get("nav", [])) != 3:
            bad(f"{code}: nav must hold three labels")
        s, p, u = t.get("s", {}), t.get("p", {}), t.get("t", {})
        for key in ("title", "meta", "eyebrow", "h1", "lead", "faqT", "cT", "cL", "cB"):
            if not s.get(key):
                bad(f"{code}: support block missing {key}")
        for key in ("title", "meta", "eyebrow", "h1", "lead", "upd", "vow", "cT", "cL", "cB"):
            if not p.get(key):
                bad(f"{code}: privacy block missing {key}")
        for key in ("title", "meta", "eyebrow", "h1", "lead", "upd", "cT", "cL", "cB"):
            if not u.get(key):
                bad(f"{code}: terms block missing {key}")
        if len(s.get("chips", [])) != CHIP_COUNT:
            bad(f"{code}: needs exactly {CHIP_COUNT} chips")
        if len(s.get("faq", [])) != FAQ_COUNT:
            bad(f"{code}: needs exactly {FAQ_COUNT} FAQ entries")
        if len(p.get("sec", [])) != SEC_COUNT:
            bad(f"{code}: needs exactly {SEC_COUNT} policy sections")
        if len(u.get("sec", [])) != TERMS_COUNT:
            bad(f"{code}: needs exactly {TERMS_COUNT} terms sections")
        for label, rows in (("faq", s.get("faq", [])), ("sec", p.get("sec", [])),
                            ("terms", u.get("sec", []))):
            for i, row in enumerate(rows, 1):
                if len(row) != 2 or not row[0].strip() or not row[1].strip():
                    bad(f"{code}: {label} entry {i} is not a filled pair")
        if code not in ENGLISH:
            if t["foot"] == en["foot"]:
                bad(f"{code}: summary is copied from English")
            if p.get("vow") == en["p"]["vow"]:
                bad(f"{code}: privacy promise is copied from English")
            if s.get("faq", [["", ""]])[0][1] == en["s"]["faq"][0][1]:
                bad(f"{code}: first FAQ answer is copied from English")
            if u.get("sec", [["", ""]])[0][1] == en["t"]["sec"][0][1]:
                bad(f"{code}: first terms section is copied from English")
        # the free tier and the purchase model must be stated in every locale
        pro = " ".join(a for _, a in s.get("faq", []))
        if "5" not in pro:
            bad(f"{code}: the free tier of 5 saves is not stated")
        check_terms_promise(code, u)


def check_terms_promise(code, block):
    """Terms must deny a subscription in this language, and quote no price."""
    rows = block.get("sec", [])
    body = " ".join(head + " " + text for head, text in rows)
    word, negation = NOSUB[code]
    hit = body.lower().find(word.lower())
    if hit < 0:
        bad(f"{code}: terms never mention the purchase model ({word})")
    else:
        window = body.lower()[max(0, hit - 70):hit + len(word) + 70]
        if negation.lower() not in window:
            bad(f"{code}: terms must state that Pro is not a subscription")
    money = " ".join([body, block.get("lead", ""), block.get("title", "")])
    if any(sym in money for sym in MONEY) or re.search(r"\d", body):
        bad(f"{code}: terms quote a price or a figure — the App Store owns that")
    if MAIL not in body:
        bad(f"{code}: terms do not give the contact address")


def check_pages():
    for name in PAGES:
        path = ROOT / name
        if not path.exists():
            bad(f"{name}: not built")
            continue
        text = path.read_text(encoding="utf-8")
        m = re.search(r"window\.SAVETAG_I18N=(\{.*?\});\n", text, re.S)
        if not m:
            bad(f"{name}: locale payload not found")
            continue
        payload = json.loads(m.group(1).replace("<\\/", "</"))
        for code in LOCALES:
            if code not in payload:
                bad(f"{name}: locale {code} missing from the switcher payload")
        for tag in ("<script src=", "<link rel=\"stylesheet\"", "@import", "fetch(",
                    "XMLHttpRequest", "googletagmanager", "google-analytics",
                    "//fonts.", "cdn."):
            if tag in text:
                bad(f"{name}: forbidden external/tracking construct {tag!r}")


def check_mail():
    for f in ROOT.rglob("*"):
        if not f.is_file() or ".git/" in str(f) or f.suffix in (".png", ".jpg", ".pyc"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for banned in BANNED:
            if banned in text:
                bad(f"{f.relative_to(ROOT)}: banned contact address {banned}")
        for addr in set(re.findall(r"[\w.+-]+@[\w.-]+\.\w+", text)):
            if addr != MAIL:
                bad(f"{f.relative_to(ROOT)}: unexpected address {addr}")


def check_app_contract():
    """The two facts most likely to drift are read straight from the app."""
    store = APP_ROOT / "SaveTag" / "Store" / "LibraryStore.swift"
    if store.exists():
        m = re.search(r"freeItemLimit\s*=\s*(\d+)", store.read_text(encoding="utf-8"))
        if m and m.group(1) != "5":
            bad(f"app free limit is {m.group(1)} but the site says 5")
    project = APP_ROOT / "project.yml"
    if project.exists() and "com.alice51849.SaveTag" not in project.read_text(
            encoding="utf-8"):
        bad("app bundle identifier no longer matches the documented product")


def check_honesty():
    """The site may only make claims that hold for the shipped app."""
    data = load_locales()
    joined = json.dumps(data["en-US"], ensure_ascii=False).lower()
    must = [
        "share sheet", "clipboard", "naturallanguage", "on your device",
        "one-time purchase", "family sharing", "markdown", "restore purchase",
        "no account", "latest 5 saves", "rediscover", "widget", "siri",
        # terms anchors: the licence, the refund route and the forum for disputes
        "non-consumable", "taiwan", "apple's policy", "as it is",
    ]
    for phrase in must:
        if phrase not in joined:
            bad(f"en-US: honesty anchor missing — {phrase!r}")
    forbidden = [
        "subscription plan", "monthly plan", "per month", "free trial",
        "chatgpt", "gpt-", "large language model",
        "hand-drawn", "hand drawn", "human voice", "voice actor",
        "military-grade", "encrypted cloud", "guaranteed",
        "no. 1", "best app", "no network requests", "never connects",
        "nothing ever leaves your device",
        "lifetime", "forever", "own it for life", "we will refund",
    ]
    for phrase in forbidden:
        if phrase in joined:
            bad(f"en-US: claim the app does not support — {phrase!r}")
    # These may only ever appear as a denial ("no cloud AI", "not a subscription")
    denied_only = ("generative ai", "generative model", "cloud ai",
                   "cloud sync", "subscription")
    negations = ("no ", "not ", "never ", "without ", "nor ", "neither ")
    for phrase in denied_only:
        for m in re.finditer(re.escape(phrase), joined):
            lead = joined[max(0, m.start() - 40):m.start()]
            if not any(n in lead for n in negations):
                bad(f"en-US: {phrase!r} must only appear as a denial — {lead[-40:]!r}")


def main():
    check_content()
    check_pages()
    check_mail()
    check_app_contract()
    check_honesty()
    if FAIL:
        for msg in FAIL:
            print("FAIL", msg)
        sys.exit(1)
    print(f"PASS  {len(LOCALES)} locales, {len(PAGES)} pages, contact {MAIL}")


if __name__ == "__main__":
    main()
