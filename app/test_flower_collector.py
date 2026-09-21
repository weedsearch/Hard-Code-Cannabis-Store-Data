import reflex as rx
import unittest
from app.flower_collector import normalize_url, parse_page


class FlowerParserTests(unittest.TestCase):
    def test_variants_and_missing_values(self):
        html = '<script type="application/ld+json">{"name":"Blue Dream","category":"Flower","offers":[{"price":"20","weight":"1g"},{"price":"40","weight":"3.5g"}]}</script>'
        rows, _, _ = parse_page(html, "https://example.com/menu", "Store")
        self.assertEqual(
            [(r["price"], r["weight"]) for r in rows],
            [("20", "1g"), ("40", "3.5g")],
        )
        self.assertEqual(rows[0]["thc"], "")

    def test_exclusions(self):
        for name in [
            "Infused Flower",
            "Pre-roll",
            "Shake",
            "Trim",
            "Kief",
            "Vape",
            "Live Rosin",
        ]:
            html = f'<script type="application/json">{{"name":"{name}","category":"Flower"}}</script>'
            self.assertEqual(
                parse_page(html, "https://example.com", "Store")[0], []
            )

    def test_no_category_no_inference(self):
        html = '<script type="application/json">{"name":"Blue Dream","price":20}</script>'
        self.assertEqual(
            parse_page(html, "https://example.com", "Store")[0], []
        )

    def test_discovery_and_provider(self):
        html = '<iframe src="https://www.iheartjane.com/stores/123"></iframe><a href="/menu">Shop</a><a href="/checkout">Order</a>'
        _, links, vendor = parse_page(html, "https://example.com", "Store")
        self.assertEqual(vendor, "jane")
        self.assertIn("https://example.com/menu", links)
        self.assertNotIn("https://example.com/checkout", links)

    def test_normalization(self):
        self.assertEqual(
            normalize_url("https://EXAMPLE.com/menu/?utm_source=x&store=1#top"),
            "https://example.com/menu?store=1",
        )
        self.assertEqual(normalize_url("javascript:alert(1)"), "")
        self.assertEqual(normalize_url("https://user:secret@example.com"), "")


if __name__ == "__main__":
    unittest.main()
