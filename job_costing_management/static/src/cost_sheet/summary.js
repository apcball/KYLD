/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { formatMonetary, formatFloat } from "@web/views/fields/formatters";
import { _t } from "@web/core/l10n/translation";

export class JobCostSheetSummary extends Component {
    static template = "job_costing_management.CostSheetSummary";
    static props = { ...standardWidgetProps };

    get data() { return this.props.record.data; }
    money(value) {
        return formatMonetary(value, { currencyId: this.data.currency_id?.[0] });
    }
    get budget() { return this.data.boq_total_cost || 0; }
    get actual() { return this.data.actual_total_cost || 0; }
    get variance() { return this.actual - this.budget; }
    get ratio() { return this.budget > 0 ? this.actual / this.budget * 100 : null; }
    get progress() { return Math.max(0, Math.min(100, this.ratio ?? 0)); }
    percent(value) { return `${formatFloat(value, { digits: [16, 1] })}%`; }
    tone(value) { return value > 0 ? "jcs_over" : value < 0 ? "jcs_under" : ""; }
    get cards() {
        return [
            { key: "budget", label: _t("Budget (BOQ)"), value: this.budget, icon: "fa-cube" },
            { key: "planned", label: _t("Active Planned"), value: this.data.active_total_cost || 0, icon: "fa-database" },
            { key: "actual", label: _t("Actual Cost"), value: this.actual, icon: "fa-file-text-o" },
            { key: "variance", label: _t("Variance"), value: this.variance, icon: "fa-line-chart" },
        ];
    }
    get breakdowns() {
        const d = this.data;
        const budget = [d.boq_material_cost || 0, d.boq_labour_cost || 0, d.boq_overhead_cost || 0];
        const actual = [d.actual_material_cost || 0, d.actual_labour_cost || 0, d.actual_overhead_cost || 0];
        const labels = [_t("Material Cost"), _t("Labour Cost"), _t("Overhead Cost")];
        const icons = ["fa-briefcase", "fa-users", "fa-cog"];
        return [
            { key: "budget", title: _t("BOQ Costs (Baseline Budget)"), values: budget, total: this.budget, footer: _t("Total (BOQ)") },
            { key: "planned", title: _t("Active Planned Costs"), values: [d.active_material_cost || 0, d.total_labour_cost || 0, d.total_overhead_cost || 0], total: d.active_total_cost || 0, footer: _t("Total Planned") },
            { key: "actual", title: _t("Actual Costs"), values: actual, total: this.actual, footer: _t("Total Actual") },
            { key: "variance", title: _t("Variance (Actual − Budget)"), values: actual.map((value, i) => value - budget[i]), total: this.variance, footer: _t("Total Variance") },
        ].map((panel) => ({ ...panel, rows: panel.values.map((value, i) => ({ label: labels[i], icon: icons[i], value })) }));
    }
}

registry.category("view_widgets").add("job_cost_sheet_summary", { component: JobCostSheetSummary });
