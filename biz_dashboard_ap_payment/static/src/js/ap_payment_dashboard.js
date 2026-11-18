/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { download } from "@web/core/network/download";
import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";

const MONTHS_TH = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
];

const COLORS = {
    cash: "#10b981",
    credit: "#2f80ed",
    ink: "#1b2a49",
};

const DONUT_COLORS = ["#2f80ed", "#f97316", "#10b981", "#7c4dff", "#f59e0b", "#9ca3af"];

function compactNumber(value) {
    const abs = Math.abs(value);
    if (abs >= 1000000) return (value / 1000000).toFixed(1).replace(/\.0$/, "") + "M";
    if (abs >= 1000) return (value / 1000).toFixed(0) + "K";
    return Math.round(value).toLocaleString("en-US");
}

function formatNumber(value, digits = 0) {
    return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    }).format(value || 0);
}

/** Draws the stack total above each bar (Chart.js ships no datalabels plugin). */
const stackTotalsPlugin = {
    id: "apdStackTotals",
    afterDatasetsDraw(chart) {
        const { ctx, data, scales } = chart;
        if (!scales.x || !scales.y || !data.datasets.length) return;
        const count = data.labels.length;
        ctx.save();
        ctx.font = "bold 11px sans-serif";
        ctx.fillStyle = COLORS.ink;
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        for (let i = 0; i < count; i++) {
            let total = 0;
            let x = null;
            data.datasets.forEach((dataset, d) => {
                if (!chart.isDatasetVisible(d)) return;
                total += Number(dataset.data[i]) || 0;
                const bar = chart.getDatasetMeta(d).data[i];
                if (bar) x = bar.x;
            });
            if (x === null || !total) continue;
            ctx.fillText(formatNumber(total), x, scales.y.getPixelForValue(total) - 4);
        }
        ctx.restore();
    },
};

/** Writes two centred lines inside a doughnut. */
function centerTextPlugin(getText) {
    return {
        id: "apdCenterText",
        afterDraw(chart) {
            const { ctx, chartArea } = chart;
            if (!chartArea) return;
            const { title, value } = getText();
            const x = (chartArea.left + chartArea.right) / 2;
            const y = (chartArea.top + chartArea.bottom) / 2;
            ctx.save();
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = COLORS.ink;
            ctx.font = "bold 16px sans-serif";
            ctx.fillText(value, x, y - 8);
            ctx.font = "12px sans-serif";
            ctx.fillStyle = "#6b7280";
            ctx.fillText(title, x, y + 12);
            ctx.restore();
        },
    };
}

export class ApPaymentDashboard extends Component {
    static template = "biz_dashboard_ap_payment.ApPaymentDashboard";

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.action = useService("action");
        const today = new Date();
        const initial = {
            month: today.getMonth() + 1,
            year: today.getFullYear(),
            company_id: "all",
            project_id: "all",
            analytic_id: "all",
            partner_id: "all",
        };
        this.state = useState({
            draft: { ...initial },
            applied: { ...initial },
            data: null,
            tab: "vendor",
            loading: false,
            exporting: false,
            exportOpen: false,
            error: "",
            detail: { open: false, loading: false, title: "", data: null, section: "bills" },
        });
        this.refs = {
            weekly: useRef("weeklyChart"),
            donut: useRef("donutChart"),
            forecast: useRef("forecastChart"),
            plan: useRef("planChart"),
        };
        this.charts = {};
        this.months = MONTHS_TH.map((name, i) => ({ id: i + 1, name }));

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.load();
        });
        onMounted(() => this.renderCharts());
        onWillUnmount(() => this.destroyCharts());
    }

    // ------------------------------------------------------------------
    // Data
    // ------------------------------------------------------------------
    /** refresh=true bypasses the server-side cache. */
    async load(refresh = false) {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.rpc("/ap_dashboard/api/data", {
                ...this.state.applied,
                refresh,
            });
        } catch (error) {
            console.error("AP dashboard load failed", error);
            this.state.error = (error && error.data && error.data.message) || String(error);
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    onDraftChange(field, ev) {
        const value = ev.target.value;
        this.state.draft[field] = field === "month" || field === "year" ? Number(value) : value;
    }

    async onApply() {
        if (this.state.loading) return;
        this.state.applied = { ...this.state.draft };
        await this.load();
        this.renderCharts();
    }

    async onRefresh() {
        if (this.state.loading) return;
        await this.load(true);
        this.renderCharts();
    }

    /** Server stamp is UTC "YYYY-MM-DD HH:MM:SS"; show browser-local HH:MM. */
    updatedTime(value) {
        if (!value) return "";
        const stamp = new Date(value.replace(" ", "T") + "Z");
        if (isNaN(stamp)) return "";
        return stamp.toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" });
    }

    setTab(id) {
        this.state.tab = id;
    }

    isSelected(field, value) {
        return String(this.state.draft[field]) === String(value);
    }

    // ------------------------------------------------------------------
    // Template helpers
    // ------------------------------------------------------------------
    get data() {
        return this.state.data;
    }

    get table() {
        return this.data ? this.data.tables[this.state.tab] : { rows: [], footer: null };
    }

    get tabMeta() {
        const tabs = (this.data && this.data.tabs) || [];
        return tabs.find((t) => t.id === this.state.tab) || { title: "", column: "" };
    }

    get options() {
        return (this.data && this.data.options) || { companies: [], projects: [], analytics: [], vendors: [], years: [] };
    }

    get years() {
        const years = new Set(this.options.years || []);
        years.add(Number(this.state.draft.year));
        return [...years].sort();
    }

    fmtBaht(value) {
        return formatNumber(value) + " บาท";
    }

    fmtNum(value) {
        if (!value) return "-";
        return formatNumber(value);
    }

    fmtPct(value) {
        return formatNumber(value || 0, Number.isInteger(value) ? 0 : 1) + "%";
    }

    barPct(value) {
        return Math.max(0, Math.min(100, value || 0));
    }

    thaiDate(iso) {
        if (!iso) return "";
        const [y, m, d] = iso.split("-").map(Number);
        return `${d} ${MONTHS_TH[m - 1]} ${y}`;
    }

    donutColor(index) {
        return DONUT_COLORS[index % DONUT_COLORS.length];
    }

    // ------------------------------------------------------------------
    // Row drill-down
    // ------------------------------------------------------------------
    async openDetail(row) {
        const detail = this.state.detail;
        Object.assign(detail, { open: true, loading: true, title: row.name, data: null, section: "bills" });
        try {
            const data = await this.rpc("/ap_dashboard/api/detail", {
                ...this.state.applied,
                tab: this.state.tab,
                key: row.key,
            });
            // ignore a stale answer when another row was opened meanwhile
            if (!detail.open || detail.title !== row.name) return;
            detail.data = data;
            const first = data.sections.find((s) => s.count);
            detail.section = first ? first.id : "bills";
        } catch (error) {
            console.error("AP dashboard detail failed", error);
            this.notification.add(
                (error && error.data && error.data.message) || "โหลดรายละเอียดไม่สำเร็จ", { type: "danger" });
            detail.open = false;
        } finally {
            detail.loading = false;
        }
    }

    closeDetail() {
        this.state.detail.open = false;
    }

    setDetailSection(id) {
        this.state.detail.section = id;
    }

    get detailSection() {
        const data = this.state.detail.data;
        return data ? data.sections.find((s) => s.id === this.state.detail.section) || data.sections[0] : null;
    }

    openRecord(row) {
        if (!row.id) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: row.model,
            res_id: row.id,
            views: [[false, "form"]],
            target: "new",
        });
    }

    kindLabel(kind) {
        return {
            cash: "โอน / เช็ค / อื่น ๆ",
            loan: "เงินยืมกรรมการ (ไม่ใช่เงินออก)",
            note: "ตั๋วเงินจ่าย (ไม่ใช่เงินออก)",
            advance: "เงินทดรอง (ไม่ใช่เงินออก)",
        }[kind] || kind;
    }

    // ------------------------------------------------------------------
    // Export
    // ------------------------------------------------------------------
    toggleExport() {
        this.state.exportOpen = !this.state.exportOpen;
    }

    closeExport() {
        this.state.exportOpen = false;
    }

    noop() {}

    async exportExcel(sheet) {
        this.state.exportOpen = false;
        if (this.state.exporting) return;
        this.state.exporting = true;
        try {
            await download({
                url: "/ap_dashboard/api/export",
                data: { ...this.state.applied, sheet: sheet || this.state.tab },
            });
        } catch (error) {
            console.error("AP dashboard export failed", error);
            this.notification.add("Export Excel ไม่สำเร็จ", { type: "danger" });
        } finally {
            this.state.exporting = false;
        }
    }

    // ------------------------------------------------------------------
    // Charts
    // ------------------------------------------------------------------
    destroyCharts() {
        Object.values(this.charts).forEach((chart) => chart.destroy());
        this.charts = {};
    }

    renderCharts() {
        if (!this.data) return;
        this.renderStacked("weekly", this.data.weekly);
        this.renderDonut();
        this.renderStacked("forecast", this.data.forecast_weekly);
        this.renderPlanDonut();
    }

    _draw(name, config) {
        const el = this.refs[name].el;
        if (this.charts[name]) {
            this.charts[name].destroy();
            delete this.charts[name];
        }
        const ChartJS = window.Chart;
        if (!el || !ChartJS) {
            if (!ChartJS) console.error("Chart.js library is not available.");
            return;
        }
        this.charts[name] = new ChartJS(el.getContext("2d"), config);
    }

    _moneyTooltip() {
        return {
            callbacks: {
                label: (ctx) => " " + ctx.dataset.label + ": " + this.fmtBaht(ctx.parsed.y ?? ctx.parsed),
            },
        };
    }

    renderStacked(name, rows) {
        const bar = (label, key, color) => ({
            label,
            data: rows.map((r) => r[key]),
            backgroundColor: color,
            borderRadius: 4,
            maxBarThickness: 64,
        });
        this._draw(name, {
            type: "bar",
            data: {
                labels: rows.map((r) => [r.label, "(" + r.range + ")"]),
                datasets: [bar("เงินสด", "cash", COLORS.cash), bar("เครดิต", "credit", COLORS.credit)],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: 22 } },
                interaction: { mode: "index", intersect: false },
                scales: {
                    x: { stacked: true, grid: { display: false } },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: { callback: compactNumber },
                        grid: { color: "rgba(0,0,0,0.05)" },
                        title: { display: true, text: "บาท" },
                    },
                },
                plugins: {
                    legend: { position: "top", align: "end", labels: { usePointStyle: true, boxWidth: 8 } },
                    tooltip: this._moneyTooltip(),
                },
            },
            plugins: [stackTotalsPlugin],
        });
    }

    renderPlanDonut() {
        const plan = this.data.kpi_plan;
        const parts = [
            { name: "ยอดหนี้ยกมา (Overdue)", amount: plan.overdue, color: "#f0385a" },
            { name: "ยอดหนี้ Due เดือนก่อน", amount: plan.prev_due, color: "#2f80ed" },
            { name: "ยอดใช้จ่ายเดือนนี้", amount: plan.month, color: "#10b981" },
            { name: "เงินเดือน + รายจ่ายอื่นๆ", amount: plan.other, color: "#7c4dff" },
        ];
        this._draw("plan", {
            type: "doughnut",
            data: {
                labels: parts.map((p) => p.name),
                datasets: [{
                    data: parts.map((p) => Math.max(p.amount, 0)),
                    backgroundColor: parts.map((p) => p.color),
                    borderWidth: 2,
                    borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (ctx) => " " + ctx.label + ": " + this.fmtBaht(ctx.parsed) } },
                },
            },
            plugins: [centerTextPlugin(() => ({ title: "เจ้าหนี้รวม", value: formatNumber(plan.total) }))],
        });
    }

    renderDonut() {
        const share = this.data.vendor_share;
        const items = share.items || [];
        this._draw("donut", {
            type: "doughnut",
            data: {
                labels: items.map((i) => i.name),
                datasets: [{
                    data: items.map((i) => i.amount),
                    backgroundColor: items.map((_, i) => this.donutColor(i)),
                    borderWidth: 2,
                    borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "66%",
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => " " + ctx.label + ": " + this.fmtBaht(ctx.parsed)
                                + " (" + this.fmtPct(items[ctx.dataIndex].pct) + ")",
                        },
                    },
                },
            },
            plugins: [centerTextPlugin(() => ({ title: "บาท", value: formatNumber(share.total) }))],
        });
    }
}

registry.category("actions").add("biz_dashboard_ap_payment.dashboard", ApPaymentDashboard);
