Please read our detailed guide about optimal picking routes in your warehouse here - https://ventor.tech/warehouse-management/how-to-build-picking-routes-in-your-warehouse-for-walking-minimization/

|

Read also Picking and Packing optimization guide - https://ventor.tech/mobile/pick-more-walk-less-full-picking-and-packing-optimization-in-odoo/

|

==========================
 Quick configuration guide
==========================

|

1. Install the Ventor Outgoing routing module on your Odoo server (and all dependencies)
2. Assign removal priority (sequence) for each location. You can do it manually or `import <https://ventor.tech/warehouse-management/how-to-build-picking-routes-in-your-warehouse-for-walking-minimization/#upload-route>`_ a .csv file

|

.. image:: images/image7.png
   :width: 800px

|

3. Go to Settings > Ventor/mERP. Set up needed Picking strategy and Reservation strategy

|

.. image:: images/image8.png
   :width: 800px

|

\*Reservation strategy available for Odoo 12 and higher

|

Change Log
##########

|

* 1.0.3 (2022-04-27)
    - Fixed reservation and removal strategy on ventor base module ignore force removal strategy on Product Category or/and Location 

* 1.0.2 (2021-11-30)
    - Fixing issue with compute method for strategy_sequence field on stock.location. That was causing issues in POS module