/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ExecutiveDashboard extends Component {
    static template = "job_costing_management.ExecutiveDashboard";
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.company = useService("company");
        this.sequence = 0;
        this.state = useState({
            loading: true, error: "", data: null,
            filters: { company_id: this.company.currentCompany.id, project_id: "",
                date_from: "", date_to: "", states: ["approved"] },
        });
        onWillStart(() => this.load());
        onWillUnmount(() => { this.sequence++; });
    }
    async load(page = 0) {
        const sequence = ++this.sequence;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("job.cost.sheet", "get_executive_dashboard", [], {
                filters: JSON.parse(JSON.stringify(this.state.filters)), page,
            });
            if (sequence === this.sequence) this.state.data = data;
        } catch (error) {
            if (sequence === this.sequence) {
                this.state.error = error.data?.message || error.message || "โหลดข้อมูลไม่สำเร็จ";
            }
        } finally {
            if (sequence === this.sequence) this.state.loading = false;
        }
    }
    async filter(event) {
        const key = event.target.name;
        this.state.filters[key] = event.target.value;
        if (key === "company_id") this.state.filters.project_id = "";
        await this.load();
    }
    async status(event) {
        const statuses = new Set(this.state.filters.states);
        if (event.target.checked) statuses.add(event.target.value);
        else statuses.delete(event.target.value);
        this.state.filters.states = [...statuses];
        await this.load();
    }
    money(value, group) {
        if (value === null) return "—";
        return new Intl.NumberFormat("th-TH", { minimumFractionDigits: group.digits,
            maximumFractionDigits: group.digits }).format(value);
    }
    percent(value) { return value === null ? "—" : `${value.toFixed(1)}%`; }
    label(key) {
        return { material: "วัสดุ", labour: "แรงงาน", overhead: "ค่าใช้จ่าย",
            over: "เกินงบ", near: "ใช้งบตั้งแต่ 90%", unbudgeted: "ยังไม่มีงบที่ใช้เปรียบเทียบได้" }[key];
    }
    bar(value, category) {
        const max = Math.max(Math.abs(category.budget), Math.abs(category.actual), 1);
        return `width: ${Math.abs(value) / max * 100}%`;
    }
    openSheet(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "job.cost.sheet",
            res_id: id, views: [[false, "form"]], target: "current" });
    }
    open(group, kind = "all", projectId = null) {
        const domain = [...this.state.data.domain];
        domain.push("|");
        domain.push(["currency_id", "=", group.currency_id]);
        // The server supplies the fallback company currency explicitly.
        domain.push(["currency_id", "=", group.is_company_currency ? false : group.currency_id]);
        if (projectId) domain.push(["project_id", "=", projectId]);
        if (kind === "budget") domain.push(["boq_total_cost", ">", 0]);
        if (kind === "unbudgeted") domain.push(["boq_total_cost", "<=", 0]);
        if (kind === "over") domain.push(["id", "in", group.over_ids]);
        return this.action.doAction({ type: "ir.actions.act_window", name: "Cost Sheet — งบ BOQ",
            res_model: "job.cost.sheet", views: [[false, "tree"], [false, "form"]], domain,
            target: "current" });
    }
}
registry.category("actions").add("job_costing_management.executive_dashboard", ExecutiveDashboard);
