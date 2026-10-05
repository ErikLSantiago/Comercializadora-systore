/** @odoo-module **/
import { Component, onWillStart, useRef, useState, onMounted } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

export class DispatchWorkstation extends Component {
    static template = 'systore_operations_dashboard.Dispatch';
    static props = ['*'];

    setup() {
        this.orm = useService('orm');
        this.action = useService('action');
        this.input = useRef('scan');
        this.sessionId = this.props.action.params.session_id;
        this.state = useState({code:'', busy:false, error:'', snapshot:null});
        onWillStart(() => this.reload());
        onMounted(() => this.focus());
    }

    focus() { this.input.el?.focus(); }

    async reload() {
        try {
            this.state.snapshot = await this.orm.call('systore.operations.dispatch.session', 'get_snapshot', [[this.sessionId]]);
        } catch (error) { this.state.error = error.data?.message || error.message; }
    }

    async keydown(event) {
        if (event.key === 'Enter') { event.preventDefault(); await this.scan(); }
    }

    async process(method, args = []) {
        if (this.state.busy) return;
        this.state.busy = true;
        this.state.error = '';
        try {
            const result = await this.orm.call('systore.operations.dispatch.session', method, [[this.sessionId], ...args]);
            this.state.snapshot = result.snapshot;
            this.state.code = '';
            if (result.action) {
                const action = {...result.action, target:'new'};
                await this.action.doAction(action, {onClose: async () => { await this.reload(); this.focus(); }});
            } else { await this.reload(); }
        } catch (error) { this.state.error = error.data?.message || error.message; }
        finally { this.state.busy = false; this.focus(); }
    }

    async scan() {
        const code = this.state.code.trim();
        if (!code) return;
        await this.process('scan_package', [code]);
    }

    async remove(id) { await this.process('remove_scan', [id]); }

    async validate() { await this.process('validate_ready'); }
}
registry.category('actions').add('systore_operations_dashboard.dispatch', DispatchWorkstation);
