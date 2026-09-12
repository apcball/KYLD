/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
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
        onMounted(() => this.load());
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
        this.state.filters.states = event.target.value === "all"
            ? ["approved", "done", "draft"] : [event.target.value];
        await this.load();
    }
    get selectedStatus() {
        return this.state.filters.states.length === 1 ? this.state.filters.states[0] : "all";
    }
    kpis(group) {
        return [
            { key: "budget", label: "BOQ Budget", icon: "file-text", color: "green", value: group.budget, hint: "งบ BOQ ปัจจุบันจาก Cost Sheet", kind: "budget" },
            { key: "active", label: "Active Planned Cost", icon: "briefcase", color: "blue", value: group.active, hint: "แผนต้นทุนที่ตัดรายการยกเลิกและปฏิเสธแล้ว", kind: "all" },
            { key: "actual", label: "Actual Cost", icon: "cubes", color: "purple", value: group.actual, hint: "ต้นทุนจริงทั้งหมด รวมงานที่ไม่มีงบ", kind: "all" },
            { key: "remaining", label: "Remaining (BOQ)", icon: "pie-chart", color: "orange", value: group.remaining, hint: "งบลบต้นทุนจริง เฉพาะ Cost Sheet ที่มีงบ", kind: "budget" },
            { key: "ratio", label: "BOQ Used", icon: "bar-chart", color: "red", value: group.ratio, hint: "ต้นทุนจริงหารงบ เฉพาะ Cost Sheet ที่มีงบ", kind: "budget" },
            { key: "count", label: "Job Cost Sheets", icon: "file-text-o", color: "blue", value: group.count, hint: "จำนวน Cost Sheet ตามตัวกรอง", kind: "all" },
        ];
    }
    compactMoney(value, group) {
        return value == null ? "—" : new Intl.NumberFormat("th-TH", {
            maximumFractionDigits: group.digits,
        }).format(value);
    }
    composition(group) {
        const colors = { material: "#3978d5", labour: "#ff922b", overhead: "#16ac7e" };
        return Object.entries(group.composition || {}).map(([key, value]) => ({
            key, label: this.label(key), value, color: colors[key],
        }));
    }
    donut(rows) {
        // A ring cannot truthfully represent negative amounts as proportions.
        if (rows.some(row => row.value < 0)) return "background: #e9eef5";
        const total = rows.reduce((sum, row) => sum + row.value, 0);
        if (!total) return "background: #e9eef5";
        let cursor = 0;
        const stops = rows.map(row => {
            const start = cursor;
            cursor += row.value / total * 100;
            return `${row.color} ${start}% ${cursor}%`;
        });
        return `background: conic-gradient(${stops.join(",")})`;
    }
    share(value, rows) {
        const total = rows.reduce((sum, row) => sum + row.value, 0);
        return rows.some(row => row.value < 0) || !total ? "—" : `${Math.round(value / total * 100)}%`;
    }
    categoryRect(value, group, index, series = 0) {
        const { min, span } = this.chartScale(group);
        const y = v => 170 - (v - min) / span * 140;
        return { x: 96 + index * 170 + series * 31,
            y: y(Math.max(0, value)), width: 27, height: Math.abs(y(value) - y(0)) };
    }
    categoryTicks(group) {
        const { min, span } = this.chartScale(group);
        return [0, 1, 2, 3, 4].map(i => ({ y: 170 - i * 35, value: min + span * i / 4 }));
    }
    axisMoney(value) {
        return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
    }
    trendChart(group) {
        const rows = group.trend || [];
        const values = rows.flatMap(row => [row.budget, row.actual, row.active]);
        const min = Math.min(0, ...values), max = Math.max(0, ...values);
        const span = max - min || 1;
        const y = value => 155 - (value - min) / span * 125;
        const x = i => rows.length === 1 ? 315 : 65 + i * 505 / (rows.length - 1);
        return {
            rows: rows.map((row, i) => ({ ...row, x: x(i), budgetY: y(row.budget), actualY: y(row.actual), activeY: y(row.active),
                showLabel: i === 0 || i === rows.length - 1 || i % Math.ceil(rows.length / 8) === 0 })),
            budget: rows.map((row, i) => `${x(i)},${y(row.budget)}`).join(" "),
            actual: rows.map((row, i) => `${x(i)},${y(row.actual)}`).join(" "),
            active: rows.map((row, i) => `${x(i)},${y(row.active)}`).join(" "),
            ticks: [0, 1, 2, 3].map(i => ({ y: 155 - i * 125 / 3, value: min + span * i / 3 })),
        };
    }
    monthLabel(month) {
        return new Intl.DateTimeFormat("th-TH", { month: "short", year: "2-digit", timeZone: "UTC" })
            .format(new Date(`${month}-01T00:00:00Z`));
    }
    varianceChart(group) {
        const rows = group.categories.map(c => ({ key: c.key, label: this.label(c.key), value: c.actual - c.budget }));
        rows.push({ key: "total", label: "Total", value: group.actual - group.budget });
        const max = Math.max(1, ...rows.map(r => Math.abs(r.value)));
        return { rows: rows.map((row, i) => ({ ...row, y: 35 + i * 38,
            x: row.value < 0 ? 250 - Math.abs(row.value) / max * 135 : 250,
            width: Math.abs(row.value) / max * 135,
            labelX: row.value < 0 ? 245 - Math.abs(row.value) / max * 135 : 255 + row.value / max * 135,
        })), ticks: [-1, -.5, 0, .5, 1].map(n => ({ x: 250 + n * 135, value: n * max })) };
    }
    signedMoney(value, group) {
        return (value > 0 ? "+" : "") + this.compactMoney(value, group);
    }
    openItems(group) {
        return this.action.doAction({ type: "ir.actions.act_window", name: "BOQ Cost Items",
            res_model: "job.cost.line", views: [[false, "tree"], [false, "form"]],
            domain: this.state.data.domain.map(term => Array.isArray(term)
                ? ["cost_sheet_id." + term[0], term[1], term[2]] : term).concat([
                ["boq_total_cost", ">", 0],
                "|", ["cost_sheet_id.currency_id", "=", group.currency_id],
                ["cost_sheet_id.currency_id", "=", group.is_company_currency ? false : group.currency_id],
            ]), target: "current" });
    }
    openItem(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "job.cost.line",
            res_id: id, views: [[false, "form"]], target: "current" });
    }
    money(value, group) {
        if (value == null) return "—";
        return new Intl.NumberFormat("th-TH", { minimumFractionDigits: group.digits,
            maximumFractionDigits: group.digits }).format(value);
    }
    percent(value) { return value === null ? "—" : `${value.toFixed(1)}%`; }
    label(key) {
        return { material: "Material", labour: "Labour", overhead: "Overhead",
            over: "เกินงบ", near: "เฝ้าระวัง", normal: "ปกติ", neutral: "ยังไม่มีงบ", unbudgeted: "ยังไม่มีงบ" }[key];
    }
    chartScale(group) {
        const values = group.categories.flatMap(category => [category.budget, category.active, category.actual]);
        const min = Math.min(0, ...values);
        const max = Math.max(0, ...values);
        return { min, span: max - min || 1 };
    }
    bar(value, group) {
        const { min, span } = this.chartScale(group);
        return `left: ${(Math.min(0, value) - min) / span * 100}%; width: ${Math.abs(value) / span * 100}%`;
    }
    zero(group) {
        const { min, span } = this.chartScale(group);
        return `left: ${-min / span * 100}%`;
    }
    utilization(value) {
        return `width: ${Math.max(0, Math.min(100, value || 0))}%`;
    }
    tone(value) {
        return value === null ? "neutral" : value > 100 ? "over" : value >= 90 ? "near" : "normal";
    }
    updatedAt(value) {
        if (!value) return "—";
        const date = new Date(value.replace(" ", "T") + "Z");
        return Number.isNaN(date.getTime()) ? value + " UTC" : new Intl.DateTimeFormat("th-TH", {
            dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok",
        }).format(date) + " (เวลาไทย)";
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
