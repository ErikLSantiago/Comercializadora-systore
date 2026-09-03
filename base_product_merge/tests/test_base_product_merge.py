# Copyright 2023 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class TestBaseProductMerge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_model = cls.env["product.product"]
        cls.base_product_merge_model = cls.env["base.product.merge"]

    def test_product_merge(self):
        # take current product count
        total_products = len(self.product_model.search([]))
        # create products
        product_1 = self.product_model.create({"name": "test product 1"})
        product_2 = self.product_model.create({"name": "test product 2"})
        product_3 = self.product_model.create({"name": "test product 3"})
        product_4 = self.product_model.create({"name": "test product 4"})

        # check product count before merge
        self.assertEqual(len(self.product_model.search([])), total_products + 4)

        # merge product_2 and product_4 with product_1
        product_merge = self.base_product_merge_model.with_context(
            active_ids=[product_1.id, product_2.id, product_4.id],
            active_model="product.product",
        ).create({})
        product_merge.dst_product_id = product_1
        product_merge.action_merge()

        # check product count before merge
        self.assertEqual(len(self.product_model.search([])), total_products + 2)
        # check product_3 exists
        self.assertTrue(product_3.exists())

    def test_destination_putaway_rules_take_precedence(self):
        location_in = self.env["stock.location"].create(
            {"name": "Merge input", "usage": "internal"}
        )
        dominant_location = self.env["stock.location"].create(
            {
                "name": "Dominant shelf",
                "usage": "internal",
                "location_id": location_in.id,
            }
        )
        duplicate_location = self.env["stock.location"].create(
            {
                "name": "Duplicate shelf",
                "usage": "internal",
                "location_id": location_in.id,
            }
        )
        dominant = self.product_model.create({"name": "Dominant SKU"})
        duplicate = self.product_model.create({"name": "Wrong SKU"})
        dominant_rule = self.env["stock.putaway.rule"].create(
            {
                "product_id": dominant.id,
                "location_in_id": location_in.id,
                "location_out_id": dominant_location.id,
            }
        )
        duplicate_rule = self.env["stock.putaway.rule"].create(
            {
                "product_id": duplicate.id,
                "location_in_id": location_in.id,
                "location_out_id": duplicate_location.id,
            }
        )

        wizard = self.base_product_merge_model.with_context(
            active_ids=[dominant.id, duplicate.id],
            active_model="product.product",
        ).create({"dst_product_id": dominant.id})
        wizard.action_merge()

        self.assertTrue(dominant_rule.exists())
        self.assertFalse(duplicate_rule.exists())
        self.assertEqual(dominant_rule.product_id, dominant)
