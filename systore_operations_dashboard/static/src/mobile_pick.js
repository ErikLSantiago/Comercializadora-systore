/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useState, useRef, useEffect } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

export class MobilePick extends Component {
    static template = 'systore_operations_dashboard.MobilePick';
    static props = ['*'];
    setup() {
        this.orm = useService('orm');
        this.action = useService('action');
        this.params = this.props.action.params;
        this.destroyed = false;
        this.scanRef = useRef('upcInput');
        this.state = useState({page:'panel', busy:false, error:'', message:'', panel:null,
            detail:null, captures:[], index:0, query:'', pageNumber:0, mode:this.params.batch_id ? 'batches' : 'pending'});
        onWillUnmount(() => { this.destroyed = true; });
        useEffect(() => { this.scanRef.el?.focus(); }, () => [this.state.page, this.state.index]);
        onWillStart(async () => {
            await this.loadPanel();
            if (this.params.picking_id || this.params.batch_id) await this.openCard(this.params);
        });
    }
    async call(method, args) { return this.orm.call('systore.operations.dashboard', method, args); }
    async run(task) {
        if (this.state.busy || this.destroyed) return;
        this.state.busy = true;
        this.state.error = '';
        try { await task(); }
        catch (error) { if (!this.destroyed) this.state.error = error.data?.message || error.message || 'No se pudo completar la operación.'; }
        finally { if (!this.destroyed) this.state.busy = false; }
    }
    async loadPanel(page = 0, mode = this.state.mode) {
        await this.run(async () => {
            const panel = await this.call('get_mobile_pick_panel', [this.params.warehouse_id,
                this.params.date || false, this.params.scope || 'date', page, mode]);
            if (this.destroyed) return;
            this.state.panel = panel;
            this.state.mode = mode;
            this.state.pageNumber = page;
            this.state.page = 'panel';
            this.state.detail = null;
            this.state.captures = [];
        });
    }
    async switchMode(mode) {
        if (mode === this.state.mode || this.state.busy) return;
        this.state.query = '';
        await this.loadPanel(0, mode);
    }
    imageURL(productId) { return `/web/image/product.product/${productId}/image_128`; }
    imageError(event) { event.target.style.visibility = 'hidden'; }
    get cards() {
        const text = this.state.query.trim().toLocaleLowerCase();
        return (this.state.panel?.cards || []).filter(card =>
            [card.name, ...card.origins, card.operation_type].join(' ').toLocaleLowerCase().includes(text));
    }
    label(state) { return ({assigned:'Listo',confirmed:'Pendiente',waiting:'En espera',draft:'Borrador',
        mixed:'Parcialmente listo',done:'Hecho',cancel:'Cancelado'})[state] || state; }
    format(value) { return new Intl.NumberFormat('es-MX', {maximumFractionDigits:3}).format(value || 0); }
    async openCard(card) {
        if (card.blocked) { this.state.error = card.blocked; return; }
        await this.run(async () => {
            const detail = await this.call('get_mobile_pick_detail', [this.params.warehouse_id,
                card.picking_id || false, card.batch_id || false]);
            if (this.destroyed) return;
            this.state.detail = detail;
            this.state.page = 'detail';
            this.state.message = '';
        });
    }
    async original() {
        const card = this.state.detail?.card;
        if (!card) return;
        await this.run(async () => {
            const action = await this.call('open_mobile_pick_native', [this.params.warehouse_id,
                card.picking_id || false, card.batch_id || false]);
            await this.action.doAction(action);
        });
    }
    async back() {
        if (this.state.busy) return;
        if (this.state.page === 'capture') { this.state.page = 'detail'; return; }
        if (this.state.page !== 'panel') { await this.loadPanel(this.state.pageNumber); return; }
        await this.run(async () => this.action.doAction({
            type:'ir.actions.client', name:'Tablero de operaciones', tag:'systore_operations_dashboard.dashboard',
            params:{warehouse_id:this.params.warehouse_id, date:this.params.date || '',
                    scope:this.params.scope || 'date', section:'pick'},
        }, {clearBreadcrumbs:true}));
    }
    async beginValidation() {
        if (this.state.busy || !this.state.detail?.can_validate) return;
        if (!this.state.captures.length) {
            this.state.captures = this.state.detail.rows.map(row => ({...row, upc:''}));
        }
        this.state.index = 0;
        this.state.error = '';
        if (this.productsToScan.length) this.state.page = 'capture';
        else await this.validate();
    }
    get productsToScan() {
        const products = new Map();
        for (const row of this.state.captures) {
            if (row.require_upc && !products.has(row.product_id)) products.set(row.product_id,row);
        }
        return [...products.values()];
    }
    get current() { return this.productsToScan[this.state.index]; }
    get currentReady() { return !!this.current?.upc.trim(); }
    get ready() {
        return this.state.captures.length > 0 && this.state.captures.every(row =>
            !row.require_upc || !!row.upc.trim());
    }
    setUPC(event) {
        if (this.state.busy || !this.current) return;
        for (const row of this.state.captures) {
            if (row.product_id === this.current.product_id) row.upc = event.target.value;
        }
    }
    next(delta) {
        if (this.state.busy) return;
        const next = this.state.index + delta;
        if (next >= 0 && next < this.productsToScan.length) {
            this.state.index = next; this.state.error = '';
        }
    }
    async validate() {
        if (!this.ready) { this.state.error = 'Complete los UPC requeridos.'; return; }
        const detail = this.state.detail;
        let result;
        await this.run(async () => {
            result = await this.call('validate_mobile_pick', [this.params.warehouse_id,
                detail.card.picking_id || false, detail.card.batch_id || false, detail.token,
                this.state.captures.map(row => ({id:row.id,upc:row.upc}))]);
        });
        if (!result || this.destroyed) return;
        if (result.action) {
            this.state.page = 'pending';
            // Native follow-up assistants retain all contexts supplied by the installed addons.
            try { await this.action.doAction({...result.action,target:'new'}, {onClose:async () => {
                await this.loadPanel();
                if (!this.destroyed) this.state.message = 'Revise el panel para continuar las operaciones pendientes.';
            }}); }
            catch (error) { this.state.error = error.data?.message || error.message; }
        } else {
            await this.loadPanel();
            this.state.message = result.complete ? 'Recolección validada. Puede continuar con la siguiente operación.' :
                'Validación enviada. Revise las operaciones que permanecen pendientes.';
        }
    }
}
registry.category('actions').add('systore_operations_dashboard.mobile_pick', MobilePick);
