/** @odoo-module **/
import { registry } from '@web/core/registry';
import { MobilePick } from './mobile_pick';

export class MobilePack extends MobilePick {
    static template = 'operations_dashboard.MobilePack';
    get section() { return this.params.section || 'pack'; }
    get isPicking() { return this.section === 'pick'; }
    get isDelivery() { return this.section === 'out'; }
    async loadPanel(page = 0) {
        await this.run(async () => {
            this.state.panel = await this.call('get_mobile_pack_panel', [this.params.warehouse_id,this.params.batch_id || false,page,this.state.query,this.section,this.state.readiness || this.params.readiness || 'complete']);
            this.state.pageNumber = page; this.state.page = 'panel'; this.state.detail = null;
            this.state.captures = []; this.state.tracking = ''; this.state.massive = false; this.state.skipTracking = false; this.state.massText = '';
        });
    }
    async openCard(card) {
        if (!card.picking_id) return;
        await this.run(async () => {
            this.state.detail = await this.call('get_mobile_pack_detail',[this.params.warehouse_id,card.picking_id,this.section]);
            this.state.quantities = {};
            for (const row of this.state.detail.rows) this.state.quantities[row.product_id] = (this.state.quantities[row.product_id] || 0) + row.qty;
            this.state.captures = this.state.detail.rows.map(row => ({...row,upc:'',serial:'',checked:false}));
            this.state.page = 'detail'; this.state.index = 0; this.state.tracking = '';
            this.state.message = ''; this.state.massive = false; this.state.skipTracking = false; this.state.massText = '';
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
            const action = await this.call('open_mobile_pack_native',[this.params.warehouse_id,this.state.detail.picking_id,this.section]);
            await this.action.doAction(action);
        });
    }
    get current() { return this.state.captures[this.state.index]; }
    beginValidation() {
        if (this.state.busy) return;
        const counts = {};
        this.state.captures = this.state.detail.rows.filter(row => {
            counts[row.product_id] = (counts[row.product_id] || 0) + 1;
            return counts[row.product_id] <= this.state.quantities[row.product_id];
        }).map(row => ({...row,upc:'',serial:'',checked:false}));
        if (!this.state.captures.length) { this.state.error = 'Registre al menos una pieza para validar.'; return; }
        this.state.index = 0; this.state.massText = ''; this.state.page = 'upc'; this.state.error = '';
    }
    setPackQuantity(row, event) {
        if (this.state.busy) return;
        const quantity = event.target.value === '' ? NaN : Number(event.target.value);
        this.state.error = '';
        if (!Number.isInteger(quantity) || quantity < 0 || quantity > row.qty) {
            this.state.error = 'Capture piezas enteras entre cero y la cantidad disponible.'; event.target.value = this.state.quantities[row.product_id]; return;
        }
        this.state.quantities[row.product_id] = quantity;
    }
    async switchReadiness(value) {
        if (this.state.busy) return;
        this.state.readiness = value;
        await this.loadPanel(0);
    }
    setUPC(event) { if (!this.state.busy) { this.current.upc = event.target.value; this.current.checked = false; } }
    async acceptUPC() {
        await this.run(async () => {
            const result = await this.call('check_mobile_pack_piece',[this.params.warehouse_id,this.state.detail.wizard_id,
                this.state.detail.token,this.current.id,this.current.upc]);
            this.current.upc = result.upc;
            if (this.state.massive) {
                for (const row of this.massRows) { row.upc = result.upc; row.checked = false; }
                this.state.massText = this.massRows.map(row => row.serial).filter(Boolean).join('\n');
                this.state.page = 'mass_serial';
            } else this.state.page = 'serial';
        });
    }
    get massRows() { return this.state.captures.filter(row => row.product_id === this.current?.product_id); }
    get massSerialCount() { return (this.state.massText || '').split(/\r?\n/).filter(line => line.trim()).length; }
    setMassive(event) {
        if (this.state.busy) return;
        this.state.massive = !!event.target.checked;
        for (const row of this.state.captures) { row.upc = ''; row.serial = ''; row.checked = false; }
        this.state.index = 0; this.state.massText = ''; this.state.error = '';
    }
    acceptMassSerials() {
        if (this.state.busy) return;
        const serials = (this.state.massText || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
        this.state.error = '';
        if (serials.length !== this.massRows.length) {
            this.state.error = `Capture exactamente ${this.massRows.length} números de serie.`; return;
        }
        const other = this.state.captures.filter(row => row.product_id !== this.current.product_id).map(row => row.serial.trim()).filter(Boolean);
        if (new Set([...other, ...serials]).size !== other.length + serials.length) {
            this.state.error = 'El NS/IMEI ya fue capturado en esta operación.'; return;
        }
        if (serials.some(serial => serial.length > 256)) { this.state.error = 'NS/IMEI inválido.'; return; }
        this.massRows.forEach((row, index) => { row.serial = serials[index]; row.checked = true; });
        const next = this.state.captures.findIndex(row => !row.checked);
        if (next >= 0) { this.state.index = next; this.state.page = 'upc'; }
        else this.state.page = 'tracking';
    }
    async acceptSerial() {
        await this.run(async () => {
            if (this.state.captures.some(row => row.id !== this.current.id && row.serial.trim() && row.serial.trim() === this.current.serial.trim())) {
                throw Error('El NS/IMEI ya fue capturado en esta operación.');
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
        if (['serial','mass_serial'].includes(this.state.page)) { this.state.page = 'upc'; return; }
        if (this.state.page === 'tracking') { this.state.page = this.state.massive ? 'mass_serial' : 'serial'; return; }
        if (this.state.page === 'upc') { this.state.page = 'detail'; return; }
        if (this.state.page !== 'panel') { await this.loadPanel(); return; }
        await this.action.doAction({type:'ir.actions.client',tag:'operations_dashboard.dashboard',
            params:{warehouse_id:this.params.warehouse_id,section:this.section}},{clearBreadcrumbs:true});
    }
    async validate() {
        if (!this.state.captures.length || this.state.captures.some(row => !row.checked)) return;
        let result;
        await this.run(async () => { result = await this.call('validate_mobile_pack',[this.params.warehouse_id,
            this.state.detail.wizard_id,this.state.detail.token,this.state.captures.map(row => ({id:row.id,upc:row.upc,serial:row.serial})),this.state.tracking,!!this.state.massive,!!this.state.skipTracking]); });
        if (!result || this.destroyed) return;
        if (result.action) {
            this.state.page = 'pending';
            try { await this.action.doAction({...result.action,target:'new'},{onClose:() => this.loadPanel()}); }
            catch (error) { this.state.error = error.data?.message || error.message; }
        } else { await this.loadPanel(); this.state.message = result.complete ? (this.isDelivery ? 'Salida validada.' : this.isPicking ? 'Recolección validada.' : 'Empaquetado validado.') : 'Revise las operaciones pendientes.'; }
    }
}
registry.category('actions').add('operations_dashboard.mobile_pack', MobilePack);
