===================
Base Products Merge
===================

Production adaptation for Odoo 18 that merges duplicate product records into
one dominant product.

Features
========

* Available only to users with the ``Unificar productos / SKU`` permission.
* Supports product and single-variant product-template selections.
* Redirects relational references to the dominant record.
* Keeps the dominant product's product-specific putaway rules by default.
* Blocks incompatible company, unit of measure, tracking, and product-type
  combinations before merging.
* Includes its required merge engine; no external Python package is required.

Important
=========

Merging is destructive and cannot be undone from the interface. Create a
database backup first and validate stock quantities and inventory valuation
after every merge. ORM respects Odoo business validations. SQL is intended only
for exceptional, reviewed cases involving genuinely duplicate products.

Credits and license
===================

The original ``base_product_merge`` addon and the embedded merge engine are
copyright ForgeFlow, Tecnativa, Opener B.V. and the Odoo Community Association
contributors, licensed under AGPL-3.0 or later.

Original projects:

* https://github.com/OCA/stock-logistics-warehouse
* https://github.com/OCA/openupgradelib
