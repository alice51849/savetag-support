# SaveTag — Official Support, Privacy & Terms Site

Static support, privacy and terms site for the iOS app **SaveTag: AI Social Bookmarks**
(on-device bookmarking with automatic topic tags, source at `~/48_SaveTag`).
Live URL: `https://alice51849.github.io/savetag-support/`

- `index.html` — support page + FAQ (9 questions per locale)
- `privacy.html` — privacy policy (9 sections per locale)
- `terms.html` — terms of use / EULA supplement (7 sections per locale)
- Pure-JS language switcher for all **50 Apple product-page locales**
- The website itself has no CDNs, external requests, web fonts, analytics or
  cookies — inline CSS + inline JS only
- Contact address everywhere: `hourstag.app@gmail.com`

Visual system matches the app's **Aurora Pearl** design: bright pearl glass over
a pink `#FC67AA` / purple `#CE5FE8` / periwinkle `#8980F7` / blue `#5A9EFA`
aurora wash, with a deep-plum dark mode.

## Per-locale URLs (for App Store Connect)

Each locale's `supportUrl` / `privacyPolicyUrl` can carry the language:

```
https://alice51849.github.io/savetag-support/?lang=ja
https://alice51849.github.io/savetag-support/privacy.html?lang=ja
https://alice51849.github.io/savetag-support/terms.html?lang=ja
```

Without `?lang=`, the page auto-detects from `navigator.languages`, remembers
the last choice in `localStorage`, and falls back to `en-US`.

## Repository layout

```
src/style.css               shared stylesheet (Aurora Pearl palette)
src/app.js                  locale renderer (vanilla JS, no dependencies)
src/page.tpl.html           page shell used for all three pages
src/locales/part-en.json    en-US, en-GB, en-AU, en-CA
src/locales/part-cjk.json   zh-Hant, zh-Hans, ja, ko
src/locales/part-eu*.json   25 European locales (de-DE … sl-SI)
src/locales/part-asia*.json 17 Asian / RTL locales (ar-SA, he, hi … or-IN)
src/terms/part-*.json       terms of use, same 50 locales in the same grouping
tools/build.py              merges locales + terms + CSS + JS into the three pages
tools/check.py              validation (locales, contact address, honesty, no external hosts)
assets/icon.png             app icon (512 px, from ~/48_SaveTag)
```

`index.html`, `privacy.html` and `terms.html` are **generated** — edit `src/`,
never the built pages. Terms live in `src/terms/` so the legal page can be
revised without touching a word of the support or privacy copy; the builder
folds each locale's terms block and its third nav label into the same row the
renderer already ships. Each locale writes its one-sentence summary once, in `foot`; the builder
copies it into both pages' meta description and the privacy lead so the promise
cannot drift between places.

## Build & validate

```bash
cd ~/48_SaveTag/SupportSiteRepo
~/00_GrowthEngine/.venv/bin/python tools/build.py     # regenerate all three pages
~/00_GrowthEngine/.venv/bin/python tools/check.py     # must print PASS
```

`check.py` asserts:
1. all 50 shipped locales have complete support, privacy and terms content, with
   the same number of chips, FAQ entries, policy sections (9) and terms
   sections (7) as English,
2. every FAQ / policy entry is a filled pair, and no non-English locale is a
   copy of the English text,
3. all three built pages embed every shipped locale in the switcher payload,
4. the banned private mail domains appear nowhere in the repository — the only
   public contact address is `hourstag.app@gmail.com`,
5. the website itself references no external host and no tracker,
6. the honesty contract below still holds, including the free-tier limit read
   straight out of `LibraryStore.swift`,
7. every locale's terms deny a subscription **in that language** (the word pair
   is listed per locale in `check.py`'s `NOSUB`) and quote no price or figure —
   what a buyer pays is whatever the App Store shows in their country.

## Publishing

The public repository is `alice51849/savetag-support`, with GitHub Pages
publishing the `main` branch root.

```bash
cd ~/48_SaveTag/SupportSiteRepo
git push origin main
gh api repos/alice51849/savetag-support/pages --jq '.status, .html_url'
```

After the site is live, set every locale's `supportUrl` and `privacyPolicyUrl`
in App Store Connect to the `?lang=<locale>` form above (missing URLs block
review), and make sure the privacy URL inside the app points at the live page.

## Editing content

1. Change the relevant `src/locales/part-*.json` entry.
2. Run `build.py`, then `check.py`.
3. Bump `UPDATED` in `tools/build.py` **and** `src/app.js` if the privacy or
   terms text changed (both hold the same date string shown as "Last updated"),
   and the `lastmod` dates in `sitemap.xml`.

## Honesty constraints (these must stay true of the app)

- Saving happens through the iOS share sheet from any app, or from the clipboard
  when SaveTag is opened.
- Topic tagging uses Apple's NaturalLanguage framework and a rule-based
  classifier, on device. There is no cloud AI service and no generative model,
  and no text is uploaded for processing. Tags remain editable by hand.
- Search ranks by closeness in meaning over titles, descriptions, tags and
  addresses, on device.
- Rediscover is a short daily review of saves that have not been opened yet.
- Free tier: every feature, latest 5 saves (`LibraryStore.freeItemLimit`).
- Pro is a one-time purchase (`com.alice51849.SaveTag.lifetime`), never a
  subscription: unlimited saves, custom tags, Markdown export and backup,
  Family Sharing.
- Link previews are fetched on device, directly from the saved site, to read the
  title and preview details. No SaveTag data, identifier or account is attached.
- No account, no cloud sync, no ads, no tracking, no analytics, no third-party
  SDKs, and no server operated by the developer.
- The Home Screen widget and the share extension read on-device data through
  Apple's app group only.
- Purchases and restores are handled entirely by Apple, and so are refunds — the
  developer cannot issue one.
- The terms add no promise the app cannot keep: no price is quoted, the licence
  supplements Apple's standard Licensed Application EULA, the app is offered as
  it is, and backups of a user's own saves are the user's responsibility because
  no server of ours holds a copy.
