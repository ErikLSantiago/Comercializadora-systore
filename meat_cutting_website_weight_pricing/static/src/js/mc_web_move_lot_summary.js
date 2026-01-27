/**
 * MC Web - Move assigned lot/serial info into the native order summary block.
 *
 * The order summary DOM differs across Odoo versions/themes. We avoid brittle
 * QWeb xpaths by rendering the block safely at the end of the payment template
 * and relocating it client-side.
 */
(function () {
    'use strict';

    function findFirst(selectors) {
        for (var i = 0; i < selectors.length; i++) {
            var el = document.querySelector(selectors[i]);
            if (el) {
                return el;
            }
        }
        return null;
    }

    function moveLotSummary() {
        var block = document.getElementById('mc_web_lot_summary_block');
        if (!block) {
            return;
        }

        // Nothing to show
        if (!block.querySelector('li')) {
            return;
        }

        // Avoid moving twice
        if (block.dataset && block.dataset.moved === '1') {
            return;
        }

        var anchor = findFirst([
            // Most common on /shop/payment with the new accordion layout
            '#o_wsale_total_accordion #cart_total',
            // Fallbacks
            '#o_wsale_total_accordion_item',
            '#o_wsale_total_accordion',
            '.o_wsale_accordion',
            '#wrapwrap'
        ]);

        if (!anchor) {
            return;
        }

        // If we found #cart_total, insert right before it; otherwise append to the container.
        var container = anchor;
        var beforeNode = null;
        if (anchor.id === 'cart_total') {
            container = anchor.parentNode;
            beforeNode = anchor;
        }

        // Make it visible and move
        block.classList.remove('d-none');
        if (beforeNode) {
            container.insertBefore(block, beforeNode);
        } else {
            container.appendChild(block);
        }
        block.dataset.moved = '1';
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', moveLotSummary);
    } else {
        moveLotSummary();
    }
})();
