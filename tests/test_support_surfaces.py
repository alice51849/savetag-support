import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMS_SHA256 = "0150674c594850e3ee345f92100152563f95030e6582366e1ac922c8b4768a96"
sys.path.insert(0, str(ROOT))

from tools import support_surfaces as surfaces  # noqa: E402


class SupportSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = surfaces.load_source()
        cls.promotions = surfaces.load_promotions(cls.data)
        cls.terms_before = (ROOT / "terms.html").read_bytes()
        cls.first_digest = surfaces.build(cls.data, cls.promotions)
        cls.first_tree = cls.route_hashes()
        cls.second_digest = surfaces.build(cls.data, cls.promotions)
        cls.second_tree = cls.route_hashes()
        cls.terms_after = (ROOT / "terms.html").read_bytes()

    @classmethod
    def route_hashes(cls):
        return {
            relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in surfaces.unique_routes(cls.data)
        }

    def test_build_is_idempotent_and_terms_are_untouched(self):
        self.assertEqual(self.first_digest, self.second_digest)
        self.assertEqual(self.first_tree, self.second_tree)
        self.assertEqual(self.terms_before, self.terms_after)
        self.assertEqual(
            hashlib.sha256(self.terms_after).hexdigest(),
            TERMS_SHA256,
        )

    def test_exact50_metadata_email_and_javascript_gate(self):
        report = surfaces.check(self.data, self.promotions)
        self.assertEqual(report["required_cells"], 150)
        self.assertEqual(report["unique_files"], 141)
        self.assertEqual(report["english_logical_routes"], 12)
        self.assertEqual(report["promotion_pages"], 141)
        self.assertGreater(report["javascript"]["unique_checked"], 0)

    def test_root_three_pages_cover_all_four_english_routes(self):
        for surface, relative in surfaces.FILES.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertEqual(text.count(surfaces.APP_CTA_START), 1, relative)
            self.assertEqual(text.count(surfaces.FAMILY_START), 1, relative)
            self.assertIn(f'data-ls-app-id="{surfaces.SAVE_TAG_APP_ID}"', text)
            payload = json.loads(
                re.search(
                    r'<script\b(?=[^>]*\bid=["\']ls-promotion-routes["\'])'
                    r'[^>]*>(.*?)</script>',
                    text,
                    re.I | re.S,
                ).group(1)
            )
            for locale in surfaces.ENGLISH_LOGICAL:
                self.assertEqual(
                    self.data["routes"][locale][surface],
                    relative,
                )
                self.assertEqual(
                    payload[locale]["url"],
                    self.promotions["_own_locales"][locale]["url"],
                )
                self.assertEqual(
                    payload[locale]["family"],
                    self.promotions["family"]["copy"][locale],
                )

    def test_every_locale_has_native_store_cta_and_family_parity(self):
        for relative, (locale, surface) in surfaces.unique_routes(self.data).items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertEqual(
                surfaces.promotion_errors(
                    self.data,
                    self.promotions,
                    relative,
                    locale,
                    surface,
                    text,
                ),
                [],
                relative,
            )

    def test_first_party_direct_campaign_contract(self):
        self.assertEqual(
            tuple(
                card["app_id"]
                for card in self.promotions["family"]["cards"]
            ),
            surfaces.FAMILY_APP_IDS,
        )
        for card in self.promotions["family"]["cards"]:
            self.assertTrue(card["first_party"])
            self.assertTrue(card["url"].startswith("https://apps.apple.com/"))
            self.assertIn("ct=sup_savetag", card["url"])
        for locale in surfaces.OFFICIAL:
            url = self.promotions["_own_locales"][locale]["url"]
            self.assertIn(f"/id{surfaces.SAVE_TAG_APP_ID}", url)
            self.assertIn(
                f"ct={surfaces.locale_campaign(locale)}",
                url,
            )

    def test_mutation_removing_cta_fails_closed(self):
        relative = "fr-CA/index.html"
        locale, surface = surfaces.unique_routes(self.data)[relative]
        text = (ROOT / relative).read_text(encoding="utf-8")
        mutated = surfaces.APP_CTA_RE.sub("", text, count=1)
        errors = surfaces.promotion_errors(
            self.data,
            self.promotions,
            relative,
            locale,
            surface,
            mutated,
        )
        self.assertTrue(
            any("App Store CTA" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
