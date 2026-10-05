/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

// Odoo 18 loads Luxon as a global library in web._assets_core.
const { DateTime } = luxon;

export class OperationsDashboard extends Component {
    static template = 'systore_operations_dashboard.Dashboard';
    static props = ['*'];

    setup() {
        this.orm = useService('orm');
        this.action = useService('action');
        this.notification = useService('notification');
        const returnState = this.props?.action?.params || {};
        this.requestId = 0;
        this.destroyed = false;
        this.state = useState({
            loading: true, opening: false, error: '', warehouses: [], warehouseId: returnState.warehouse_id || null,
            today: '', date: returnState.date || '', scope: returnState.scope || 'date', activeSection: returnState.section || 'in', data: null,
        });
        onWillStart(() => this.reload());
        onWillUnmount(() => { this.destroyed = true; this.requestId++; });
    }

    get activeSection() {
        return this.state.data?.sections.find(s => s.key === this.state.activeSection);
    }

    get dateLabel() {
        if (this.state.scope === 'all') return 'Todas las pendientes';
        if (this.state.scope === 'overdue') return 'Atrasadas';
        if (this.state.scope === 'undated') return 'Sin fecha';
        if (this.state.date === this.state.today) return 'Hoy';
        if (this.state.date === this.tomorrow) return 'Mañana';
        return this.displayDate(this.state.date);
    }

    get tomorrow() {
        return DateTime.fromISO(this.state.today).plus({ days: 1 }).toISODate();
    }

    format(value) {
        return new Intl.NumberFormat('es-MX').format(value || 0);
    }

    isReceipt(key) { return key === 'in' || key === 'storage'; }

    displayDate(value) {
        return value ? DateTime.fromISO(value).toFormat('dd/MM/yyyy') : 'Sin fecha';
    }

    stateLabel(value) {
        return ({ draft: 'Borrador', waiting: 'En espera', confirmed: 'Por preparar',
            assigned: 'Lista', done: 'Hecha', cancel: 'Cancelada' })[value] || value;
    }

    async reload(relativeDay = null) {
        const requestId = ++this.requestId;
        this.state.loading = true;
        this.state.error = '';
        // Never leave stale rows enabled after an authorization or network error.
        this.state.data = null;
        try {
            const config = await this.orm.call('systore.operations.dashboard', 'get_configuration', []);
            if (this.destroyed || requestId !== this.requestId) return;
            this.state.warehouses = config.warehouses;
            this.state.today = config.today;
            if (relativeDay === 'today' || relativeDay === 'tomorrow') {
                this.state.date = relativeDay === 'today' ? config.today : this.tomorrow;
            }
            if (!this.state.date) this.state.date = config.today;
            if (!config.warehouses.some(w => w.id === this.state.warehouseId)) {
                this.state.warehouseId = null;
            }
            if (!this.state.warehouseId) return;
            const data = await this.orm.call('systore.operations.dashboard', 'get_dashboard', [
                this.state.warehouseId, this.state.date, this.state.scope,
            ]);
            if (this.destroyed || requestId !== this.requestId) return;
            this.state.data = data;
            this.state.today = data.today;
            if (!data.sections.some(section => section.key === this.state.activeSection)) {
                this.state.activeSection = data.sections[0]?.key || 'transfers';
            }
        } catch (error) {
            if (!this.destroyed && requestId === this.requestId) {
                this.state.error = error.data?.message || error.message || 'No fue posible consultar las operaciones.';
            }
        } finally {
            if (!this.destroyed && requestId === this.requestId) this.state.loading = false;
        }
    }

    async selectWarehouse(id) {
        if (this.state.loading) return;
        this.state.warehouseId = id;
        await this.reload();
    }
    async warehouseHome() {
        if (this.state.loading) return;
        this.state.warehouseId = null;
        await this.reload();
    }
    async openMobileReceipt(row = null) {
        if (this.state.opening || this.state.loading || !this.state.data) return;
        this.state.opening = true;
        try {
            const action = await this.orm.call('systore.operations.dashboard', 'open_mobile_receipt', [
                this.state.warehouseId, this.state.date, this.state.scope, row?.purchase_id || false]);
            await this.action.doAction(action);
        } catch (error) { this.notification.add(error.data?.message || error.message, {type:'danger'}); }
        finally { if (!this.destroyed) this.state.opening = false; }
    }

    async chooseDate(event) {
        if (!DateTime.fromISO(event.target.value).isValid) return;
        this.state.date = event.target.value;
        this.state.scope = 'date';
        await this.reload();
    }

    async filter(kind) {
        if (kind === 'today' || kind === 'tomorrow') {
            this.state.date = kind === 'today' ? this.state.today : this.tomorrow;
            this.state.scope = 'date';
        } else {
            this.state.scope = kind;
        }
        await this.reload(kind === 'today' || kind === 'tomorrow' ? kind : null);
    }

    async openOperations(section, row = null) {
        if (this.state.opening || this.state.loading || !this.state.data) return;
        this.state.opening = true;
        try {
            const guided = ['pack', 'out'].includes(section);
            const args = [this.state.warehouseId, section, this.state.date, !this.isReceipt(section) ? 'all' : this.state.scope];
            if (guided) { args.push(row?.picking_id || false, row?.batch_id || false); }
            else { args.push(row?.purchase_id || false, row?.picking_id || false); }
            const action = await this.orm.call('systore.operations.dashboard', guided ? 'open_guided_operation' : 'open_operations', args);
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error.data?.message || error.message || 'No fue posible abrir la operación.',
                { type: 'danger' });
        } finally {
            if (!this.destroyed) this.state.opening = false;
        }
    }

    async openMobilePack(row = null) {
        if (this.state.opening || this.state.loading || !this.state.data) return;
        this.state.opening = true;
        try {
            const action = await this.orm.call('systore.operations.dashboard', 'open_mobile_pack', [
                this.state.warehouseId, row?.picking_id || false, row?.batch_id || false]);
            await this.action.doAction(action);
        } catch (error) { this.notification.add(error.data?.message || error.message, {type:'danger'}); }
        finally { if (!this.destroyed) this.state.opening = false; }
    }

    async openMobilePick(row = null) {
        if (this.state.opening || this.state.loading || !this.state.data) return;
        this.state.opening = true;
        try {
            const action = await this.orm.call('systore.operations.dashboard', 'open_mobile_pick', [
                this.state.warehouseId, this.state.date, this.state.scope,
                row?.picking_id || false, row?.batch_id || false]);
            await this.action.doAction(action);
        } catch (error) { this.notification.add(error.data?.message || error.message, {type:'danger'}); }
        finally { if (!this.destroyed) this.state.opening = false; }
    }

    async openBatches(section) {
        if (this.state.opening || this.state.loading) return;
        this.state.opening = true;
        try {
            const action = await this.orm.call('systore.operations.dashboard', 'open_batches', [
                this.state.warehouseId, section, this.state.date, !this.isReceipt(section) ? 'all' : this.state.scope]);
            await this.action.doAction(action);
        } catch (error) { this.notification.add(error.data?.message || error.message, {type:'danger'}); }
        finally { if (!this.destroyed) this.state.opening = false; }
    }
}

registry.category('actions').add('systore_operations_dashboard.dashboard', OperationsDashboard);
