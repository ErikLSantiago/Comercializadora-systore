# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
  "name"                 :  "Product Variant Extra Price",
  "summary"              :  """
                                This module allows you to manually apply additional extra prices for Product's variants.
                                manage extra price for variant extra price product price webkul products price
                            """,
  "category"             :  "Extra Tools",
  "version"              :  "1.1",
  "sequence"             :  1,
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "website"              :  "https://store.webkul.com/Odoo-Product-Variant-Extra-Price.html",
  "description"          :  """====================
**Help and Support**
====================
.. |icon_features| image:: variant_price_extra/static/src/img/icon-features.png
.. |icon_support| image:: variant_price_extra/static/src/img/icon-support.png
.. |icon_help| image:: variant_price_extra/static/src/img/icon-help.png

|icon_help| `Help <http://webkul.uvdesk.com/en/customer/create-ticket/>`_ |icon_support| `Support <http://webkul.uvdesk.com/en/customer/create-ticket/>`_ |icon_features| `Request new Feature(s) <http://webkul.uvdesk.com/en/customer/create-ticket/>`_""",
  "live_test_url"        :  "http://odoodemo.webkul.com/?module=variant_price_extra",
  "depends"              :  ['product'],
  "data"                 :  ['views/product_inherit_view.xml'],
  "images"               :  ['static/description/Banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
  "price"                :  20,
  "currency"             :  "USD",
  "pre_init_hook"        :  "pre_init_check",
}
