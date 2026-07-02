import unittest

from stoplist_logic import (
    build_product_lookup,
    build_report_text,
    collect_stoplist_products,
    extract_org_number,
    should_skip_org,
)


class StoplistLogicTest(unittest.TestCase):
    def test_collect_stoplist_products_filters_and_deduplicates(self):
        nomenclature = {
            "productCategories": [
                {"id": "cat-food", "name": "Роллы"},
                {"id": "cat-drinks", "name": "Напитки"},
                {"id": "cat-sauce", "name": "Соусы"},
            ],
            "products": [
                {"id": "p1", "name": "Филадельфия", "productCategoryId": "cat-food"},
                {"id": "p2", "name": "Филадельфия", "productCategoryId": "cat-food"},
                {"id": "p3", "name": "Кола", "productCategoryId": "cat-drinks"},
                {"id": "p4", "name": "Морс клюква", "productCategoryId": "cat-drinks"},
                {"id": "p5", "name": "Сырный соус", "productCategoryId": "cat-sauce"},
            ],
        }
        stop_list = {
            "terminalGroupStopLists": [
                {
                    "items": [
                        {
                            "items": [
                                {"productId": "p1"},
                                {"productId": "p2"},
                                {"productId": "p3"},
                                {"productId": "p4"},
                                {"productId": "p5"},
                                {"productId": "missing"},
                            ]
                        }
                    ]
                }
            ]
        }

        product_names, product_categories = build_product_lookup(nomenclature)

        self.assertEqual(
            collect_stoplist_products(stop_list, product_names, product_categories),
            ["Филадельфия", "Морс клюква"],
        )

    def test_report_helpers_sort_and_skip(self):
        self.assertEqual(extract_org_number("12. Скандинавия"), 12)
        self.assertEqual(extract_org_number("Склад 7"), 7)
        self.assertTrue(should_skip_org("4. Рязань"))

        report = build_report_text(
            {
                "12. Филиал Б": ["Сет"],
                "2. Филиал А": ["Ролл"],
            }
        )

        self.assertLess(report.index("2. Филиал А"), report.index("12. Филиал Б"))


if __name__ == "__main__":
    unittest.main()
