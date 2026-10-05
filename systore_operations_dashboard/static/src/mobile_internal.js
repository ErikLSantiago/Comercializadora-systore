/** @odoo-module **/
import { registry } from '@web/core/registry';
import { MobilePick } from './mobile_pick';
export class MobileInternal extends MobilePick {
    static template = 'systore_operations_dashboard.MobileInternal';
    get title() { return this.params.section === 'storage' ? 'Almacenamiento' : 'Transferencias'; }
    args() { return [this.params.warehouse_id,this.params.section]; }
    async loadPanel(page = 0) {
        await this.run(async () => {
            this.state.panel = await this.call('get_mobile_internal_panel',[...this.args(),this.params.date || false,this.params.scope || 'all',page,this.state.query]);
            this.state.page = 'panel'; this.state.pageNumber = page; this.state.detail = null;
        });
    }
    async openCard(card) {
        await this.run(async () => {
            this.state.detail = await this.call('get_mobile_internal_detail',[...this.args(),card.picking_id]);
            this.state.page = 'detail'; this.state.message = '';
        });
    }
    async original() {
        await this.run(async () => this.action.doAction(await this.call('open_mobile_internal_native',[...this.args(),this.state.detail.picking_id])));
    }
    async back() {
        if (this.state.busy) return;
        if (this.state.page !== 'panel') { await this.loadPanel(this.state.pageNumber); return; }
        await this.action.doAction({type:'ir.actions.client',tag:'systore_operations_dashboard.dashboard',params:{warehouse_id:this.params.warehouse_id,section:this.params.section,date:this.params.date,scope:this.params.scope}},{clearBreadcrumbs:true});
    }
    async validate() {
        let result;
        await this.run(async () => {
            result = await this.call('validate_mobile_internal',[...this.args(),this.state.detail.picking_id,this.state.detail.token,
                this.state.detail.rows.map(row => ({id:row.id,quantity:row.quantity}))]);
        });
        if (!result || this.destroyed) return;
        if (result.action) {
            this.state.page = 'pending';
            try { await this.action.doAction({...result.action,target:'new'},{onClose:() => this.loadPanel()}); }
            catch (error) { this.state.error = error.data?.message || error.message; }
        } else { await this.loadPanel(); this.state.message = result.complete ? 'Operación validada.' : 'Revise la operación pendiente.'; }
    }
}
registry.category('actions').add('systore_operations_dashboard.mobile_internal', MobileInternal);
