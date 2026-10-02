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
        this.scanRef = useRef('serialInput');
        this.state = useState({page:'panel', busy:false, error:'', message:'', panel:null,
            detail:null, captures:[], guides:{}, index:0, code:'', query:'', pageNumber:0});
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
    async loadPanel(page = 0) {
        await this.run(async () => {
            const panel = await this.call('get_mobile_pick_panel', [this.params.warehouse_id,
                this.params.date || false, this.params.scope || 'date', page]);
            if (this.destroyed) return;
            this.state.panel = panel;
            this.state.pageNumber = page;
            this.state.page = 'panel';
            this.state.detail = null;
            this.state.captures = [];
        });
    }
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
    beginValidation() {
        if (this.state.busy || !this.state.detail?.can_validate) return;
        // Retain unsent scans when returning from the capture step.
        if (!this.state.captures.length) {
            this.state.captures = this.state.detail.rows.map(row => ({...row,
                serials:[...row.existing_serials], upc:''}));
            this.state.guides = Object.fromEntries(this.state.detail.guides.map(g => [String(g.picking_id),g.value]));
        }
        this.state.index = 0;
        this.state.code = '';
        this.state.error = '';
        this.state.page = 'capture';
    }
    get current() { return this.state.captures[this.state.index]; }
    get captureCount() { return this.state.captures.reduce((sum,row) => sum + row.serials.length,0); }
    get requiredCount() { return this.state.detail?.rows.reduce((sum,row) => sum + row.qty,0) || 0; }
    get currentReady() { return !!this.current && this.current.serials.length === this.current.qty &&
        (!this.current.require_upc || !!this.current.upc.trim()); }
    get ready() {
        return this.state.captures.length > 0 && this.state.captures.every(row => row.serials.length === row.qty &&
            (!row.require_upc || !!row.upc.trim())) &&
            this.state.detail.guides.every(g => !!this.state.guides[String(g.picking_id)]?.trim());
    }
    scan(event) {
        event?.preventDefault();
        if (this.state.busy || !this.current) return;
        const serial = this.state.code.trim();
        if (!serial) return;
        if (this.current.serials.length >= this.current.qty) {
            this.state.error = 'Ya capturó todas las series de este producto.'; return;
        }
        if (this.state.captures.some(row => row.picking_id === this.current.picking_id && row.serials.includes(serial))) {
            this.state.error = 'Esta serie ya está capturada en la operación.'; return;
        }
        if (this.current.tracking === 'serial' && this.current.lot !== serial) {
            this.state.error = 'La serie no coincide con la serie nativa reservada.'; return;
        }
        this.current.serials.push(serial);
        this.state.code = '';
        this.state.error = '';
        this.scanRef.el?.focus();
    }
    removeSerial(serial) {
        if (this.state.busy || this.current.existing_serials.includes(serial)) return;
        this.current.serials = this.current.serials.filter(value => value !== serial);
    }
    next(delta) {
        if (this.state.busy) return;
        const next = this.state.index + delta;
        if (next >= 0 && next < this.state.captures.length) {
            this.state.index = next; this.state.code = ''; this.state.error = '';
        }
    }
    async validate() {
        if (!this.ready) { this.state.error = 'Complete las series, UPC y guías requeridas.'; return; }
        const detail = this.state.detail;
        let result;
        await this.run(async () => {
            result = await this.call('validate_mobile_pick', [this.params.warehouse_id,
                detail.card.picking_id || false, detail.card.batch_id || false, detail.token,
                this.state.captures.map(row => ({id:row.id,serials:[...row.serials],upc:row.upc})),
                {...this.state.guides}]);
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
