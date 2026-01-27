/** @odoo-module **/
/**
 * Move the "Unidad de peso asignada" block into the checkout/order summary sidebar.
 * We avoid brittle QWeb xpaths (they vary by theme/version).
 */
function mcMoveLotBlock() {
    const block = document.getElementById("mc_web_lot_block");
    if (!block) return;

    const selectors = [
        ".o_wsale_payment_summary",
        ".o_wsale_checkout_summary",
        ".o_wsale_cart_summary",
        "#order_summary",
        "#o_wsale_order_summary",
        ".o_wsale_sidebar",
        "aside",
    ];

    let target = null;
    for (const sel of selectors) {
        target = document.querySelector(sel);
        if (target) break;
    }

    block.classList.remove("d-none");
    if (target) {
        target.appendChild(block);
    }
}

document.addEventListener("DOMContentLoaded", mcMoveLotBlock);
window.addEventListener("load", mcMoveLotBlock);
