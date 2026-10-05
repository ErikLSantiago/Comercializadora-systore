/** @odoo-module **/
import { registry } from '@web/core/registry';
import { MobilePick } from './mobile_pick';

export class MobilePack extends MobilePick {
    static template = 'systore_operations_dashboard.MobilePack';
    async loadPanel(page = 0) {
        await this.run(async () => {
            this.state.panel = await this.call('get_mobile_pack_panel', [this.params.warehouse_id,this.params.batch_id || false,page,this.state.query]);
            this.state.pageNumber = page; this.state.page = 'panel'; this.state.detail = null;
            this.state.captures = []; this.state.tracking = '';
        });
    }
    async openCard(card) {
        if (!card.picking_id) return;
        await this.run(async () => {
            this.state.detail = await this.call('get_mobile_pack_detail',[this.params.warehouse_id,card.picking_id]);
            this.state.captures = this.state.detail.rows.map(row => ({...row,upc:'',serial:'',checked:false}));
            this.state.page = 'detail'; this.state.index = 0; this.state.tracking = '';
            this.state.message = '';
        });
    }
    get productRows() {
        const grouped = new Map();
        for (const row of this.state.detail?.rows || []) {
            if (!grouped.has(row.product_id)) grouped.set(row.product_id,{...row,qty:0});
            grouped.get(row.product_id).qty += row.qty;
        }
        return [...grouped.values()];
    }
    async original() {
        await this.run(async () => {
            const action = await this.call('open_mobile_pack_native',[this.params.warehouse_id,this.state.detail.picking_id]);
            await this.action.doAction(action);
        });
    }
    get current() { return this.state.captures[this.state.index]; }
    beginValidation() { if (!this.state.busy) { this.state.page = 'upc'; this.state.error = ''; } }
    setUPC(event) { if (!this.state.busy) { this.current.upc = event.target.value; this.current.checked = false; } }
    async acceptUPC() {
        await this.run(async () => {
            const result = await this.call('check_mobile_pack_piece',[this.params.warehouse_id,this.state.detail.wizard_id,
                this.state.detail.token,this.current.id,this.current.upc]);
            this.current.upc = result.upc; this.state.page = 'serial';
        });
    }
    async acceptSerial() {
        await this.run(async () => {
            if (this.state.captures.some(row => row.id !== this.current.id && row.serial.trim() && row.serial.trim() === this.current.serial.trim())) {
                throw Error('El NS/IMEI ya fue capturado en este empaque.');
            }
            const result = await this.call('check_mobile_pack_piece',[this.params.warehouse_id,this.state.detail.wizard_id,
                this.state.detail.token,this.current.id,this.current.upc,this.current.serial]);
            this.current.serial = result.serial; this.current.checked = true;
            if (this.state.index + 1 < this.state.captures.length) { this.state.index++; this.state.page = 'upc'; }
            else this.state.page = 'tracking';
        });
    }
    async back() {
        if (this.state.busy) return;
        this.state.error = '';
        if (this.state.page === 'serial') { this.state.page = 'upc'; return; }
        if (this.state.page === 'tracking') { this.state.page = 'serial'; return; }
        if (this.state.page === 'upc') { this.state.page = 'detail'; return; }
        if (this.state.page !== 'panel') { await this.loadPanel(); return; }
        await this.action.doAction({type:'ir.actions.client',tag:'systore_operations_dashboard.dashboard',
            params:{warehouse_id:this.params.warehouse_id,section:'pack'}},{clearBreadcrumbs:true});
    }
    async validate() {
        if (!this.state.captures.length || this.state.captures.some(row => !row.checked)) return;
        let result;
        await this.run(async () => { result = await this.call('validate_mobile_pack',[this.params.warehouse_id,
            this.state.detail.wizard_id,this.state.detail.token,this.state.captures.map(row => ({id:row.id,upc:row.upc,serial:row.serial})),this.state.tracking]); });
        if (!result || this.destroyed) return;
        if (result.action) {
            this.state.page = 'pending';
            try { await this.action.doAction({...result.action,target:'new'},{onClose:() => this.loadPanel()}); }
            catch (error) { this.state.error = error.data?.message || error.message; }
        } else { await this.loadPanel(); this.state.message = result.complete ? 'Empaquetado validado.' : 'Revise las operaciones pendientes.'; }
    }
}
registry.category('actions').add('systore_operations_dashboard.mobile_pack', MobilePack);
