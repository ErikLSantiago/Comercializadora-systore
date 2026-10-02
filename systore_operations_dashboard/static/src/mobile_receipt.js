/** @odoo-module **/
import { registry } from '@web/core/registry';
import { MobilePick } from './mobile_pick';

export class MobileReceipt extends MobilePick {
    static template = 'systore_operations_dashboard.MobileReceipt';
    async loadPanel(page = 0) {
        await this.run(async () => {
            const panel = await this.call('get_mobile_receipt_panel', [this.params.warehouse_id,
                this.params.date || false, this.params.scope || 'date', this.params.purchase_id || false, page]);
            if (this.destroyed) return;
            this.state.panel = panel; this.state.pageNumber = page; this.state.page = 'panel';
            this.state.detail = null; this.state.captures = []; this.state.receiptCard = null;
        });
    }
    async openCard(card) {
        this.state.receiptCard = card;
        this.state.purchaseId = card.purchase_id || false;
        if (card.receipts?.length > 1) { this.state.page = 'operations'; return; }
        const pickingId = card.picking_id || card.receipts?.[0]?.picking_id;
        if (pickingId) await this.openReceipt(pickingId);
    }
    async openReceipt(pickingId) {
        await this.run(async () => {
            const detail = await this.call('get_mobile_receipt_detail', [this.params.warehouse_id,
                pickingId, this.state.purchaseId || false]);
            if (this.destroyed) return;
            this.state.detail = detail; this.state.page = 'detail'; this.state.captures = [];
            this.state.message = '';
        });
    }
    async back() {
        if (this.state.busy) return;
        if (this.state.page === 'capture') { this.state.page = 'detail'; return; }
        if (this.state.page === 'detail' && this.state.receiptCard?.receipts?.length > 1) {
            this.state.page = 'operations'; return;
        }
        if (this.state.page !== 'panel') { await this.loadPanel(this.state.pageNumber); return; }
        await this.run(async () => this.action.doAction({type:'ir.actions.client', name:'Tablero de operaciones',
            tag:'systore_operations_dashboard.dashboard', params:{warehouse_id:this.params.warehouse_id,
                date:this.params.date || '',scope:this.params.scope || 'date',section:'in'}}, {clearBreadcrumbs:true}));
    }
    async original() {
        await this.run(async () => {
            const action = await this.call('open_mobile_receipt_native', [this.params.warehouse_id,
                this.state.detail.picking_id, this.state.purchaseId || false]);
            await this.action.doAction(action);
        });
    }
    async beginValidation() {
        if (this.state.busy || !this.state.detail?.can_validate) return;
        if (this.state.detail.rows.some(row => !Number.isFinite(row.quantity) || row.quantity < 0 || row.quantity > row.qty) ||
            !this.state.detail.rows.some(row => row.quantity > 0)) {
            this.state.error = 'Revise las cantidades a ingresar.'; return;
        }
        const previous = new Map(this.state.captures.map(row => [row.id,row]));
        this.state.captures = this.state.detail.rows.map(row => ({...row,upc:previous.get(row.id)?.upc || '',
            upc_checked:previous.get(row.id)?.upc_checked || false}));
        this.state.index = 0; this.state.error = '';
        if (this.productsToScan.length) this.state.page = 'capture';
        else await this.validate();
    }
    async next(delta) {
        if (this.state.busy) return;
        if (delta < 0) { if (this.state.index > 0) this.state.index--; this.state.error = ''; return; }
        if (!this.currentReady) return;
        const product = this.current;
        await this.run(async () => {
            const result = await this.call('check_mobile_receipt_upc', [this.params.warehouse_id,
                this.state.detail.picking_id, this.state.purchaseId || false, this.state.detail.token,
                product.product_id, product.upc]);
            if (this.destroyed) return;
            product.upc = result.upc; product.upc_checked = true;
            if (this.state.index + 1 < this.productsToScan.length) this.state.index++;
        });
        if (!this.destroyed && this.state.error) { this.scanRef.el?.focus(); this.scanRef.el?.select?.(); }
    }
    async validate() {
        if (!this.ready) { this.state.error = 'Complete los UPC requeridos.'; return; }
        let result;
        await this.run(async () => {
            result = await this.call('validate_mobile_receipt', [this.params.warehouse_id,
                this.state.detail.picking_id, this.state.purchaseId || false, this.state.detail.token,
                this.state.captures.map(row => ({id:row.id,quantity:row.quantity,upc:row.upc}))]);
        });
        if (!result || this.destroyed) return;
        if (result.action) {
            this.state.page = 'pending';
            try {
                await this.action.doAction({...result.action,target:'new'}, {onClose:async () => {
                    await this.loadPanel();
                    if (!this.destroyed) this.state.message = 'Revise los ingresos pendientes después de completar el asistente.';
                }});
            } catch (error) { this.state.error = error.data?.message || error.message; }
        } else {
            await this.loadPanel();
            this.state.message = result.complete ? 'Ingreso validado.' : 'Revise las operaciones pendientes.';
        }
    }
}
registry.category('actions').add('systore_operations_dashboard.mobile_receipt', MobileReceipt);
