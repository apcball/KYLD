/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { download } from "@web/core/network/download";
import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";

const COLORS = {
    limit: "#2f80ed",
    used: "#f0385a",
    reserved: "#f59e0b",
    forecast: "#7c4dff",
    available: "#10b981",
    payment: "#10b981",
};

const COMPANY_COLORS = [
    "#2f80ed", "#f59e0b", "#10b981", "#7c4dff", "#f0385a",
    "#0ea5e9", "#84cc16", "#ec4899", "#14b8a6", "#a16207",
];

const MONTHS = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
];

function compactNumber(value) {
    const abs = Math.abs(value);
    if (abs >= 1000000) return (value / 1000000).toFixed(1) + "M";
    if (abs >= 1000) return (value / 1000).toFixed(0) + "K";
    return value.toLocaleString();
}

export class WeeklyBudgetDashboard extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.state = useState({
            summary: {},
            weekly: [],
            plans: [],
            departments: [],
            payments: [],
            paymentCompanies: [],
            companies: [],
            years: [],
            months: [{ id: "all", name: "ทุกเดือน" }].concat(
                MONTHS.map((name, i) => ({ id: i + 1, name }))
            ),
            selectedCompanyId: "all",
            selectedPlanId: "all",
            selectedYear: "all",
            selectedMonth: "all",
            updatedAt: "",
            loaded: false,
            refreshing: false,
        });
        this.refs = {
            department: useRef("chart"),
            weekly: useRef("lineChart"),
            paymentGrid: useRef("paymentGrid"),
        };
        this.charts = {};

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.loadData();
            this.state.loaded = true;
        });
        onMounted(() => this.renderAll());
        onWillUnmount(() => {
            Object.values(this.charts).flat().forEach((chart) => chart.destroy());
            this.charts = {};
        });
    }

    // ------------------------------------------------------------------
    // Data
    // ------------------------------------------------------------------
    async loadData() {
        try {
            const data = await this.rpc("/budget/api/dashboard_data", {
                selectedCompanyId: this.state.selectedCompanyId,
                selectedPlanId: this.state.selectedPlanId,
                selectedYear: this.state.selectedYear,
                selectedMonth: this.state.selectedMonth,
            });
            this.state.summary = data.summary || {};
            this.state.weekly = data.weekly || [];
            this.state.departments = data.departments || [];
            this.state.payments = data.payments_monthly || [];
            this.state.paymentCompanies = data.payment_companies || [];
            this.state.companies = data.companies || [];
            this.state.plans = data.plans || [];
            this.state.years = [
                ...new Set(this.state.plans.map((plan) => plan.year).filter(Boolean)),
            ].sort();
            this.state.updatedAt = this.formatStamp(data.updated_at);
        } catch (error) {
            console.error("Failed to load dashboard data", error);
        }
    }

    async reload(field, ev) {
        this.state[field] = ev.target.value;
        await this.loadData();
        this.renderAll();
    }
    async onRefresh() {
        if (this.state.refreshing) return;
        this.state.refreshing = true;
        try {
            await this.loadData();
            this.renderAll();
        } finally {
            this.state.refreshing = false;
        }
    }
    onCompanyChange(ev) { return this.reload("selectedCompanyId", ev); }
    onPlanChange(ev) { return this.reload("selectedPlanId", ev); }
    onYearChange(ev) { return this.reload("selectedYear", ev); }
    onMonthChange(ev) { return this.reload("selectedMonth", ev); }

    // ------------------------------------------------------------------
    // Template helpers
    // ------------------------------------------------------------------
    isSelected(field, value) {
        return String(this.state[field]) === String(value);
    }

    get kpis() {
        const s = this.state.summary;
        const pct = (value) => (value || 0).toFixed(1) + "%";
        const bar = (value) => Math.max(0, Math.min(100, value || 0));
        return [
            { key: "total", label: "Total Budget", icon: "fa-database", value: this.formatCurrency(s.total_budget), sub: "งบประมาณทั้งหมด", pct: null },
            { key: "used", label: "Used (Billed)", icon: "fa-credit-card", value: this.formatCurrency(s.total_used), sub: pct(s.used_pct) + " ของงบประมาณ", pct: s.used_pct, barWidth: bar(s.used_pct) },
            { key: "reserved", label: "Reserved", icon: "fa-clock-o", value: this.formatCurrency(s.total_reserved), sub: pct(s.reserved_pct) + " ของงบประมาณ", pct: s.reserved_pct, barWidth: bar(s.reserved_pct) },
            { key: "forecast", label: "Forecast", icon: "fa-calendar", value: this.formatCurrency(s.forecast), sub: pct(s.forecast_pct) + " ของงบประมาณ", pct: s.forecast_pct, barWidth: bar(s.forecast_pct) },
            { key: "available", label: "Available", icon: "fa-shopping-bag", value: this.formatCurrency(s.remaining), sub: pct(s.available_pct) + " ของงบประมาณ", pct: s.available_pct, barWidth: bar(s.available_pct) },
            { key: "utilized", label: "Utilized %", icon: "fa-pie-chart", value: pct(s.utilization), sub: "เทียบงบประมาณ", pct: s.utilization, barWidth: bar(s.utilization) },
        ];
    }

    get legend() {
        const s = this.state.summary;
        return [
            { label: "Used (Billed)", color: COLORS.used, amount: this.formatCurrency(s.total_used), pct: (s.used_pct || 0).toFixed(1) + "%" },
            { label: "Reserved", color: COLORS.reserved, amount: this.formatCurrency(s.total_reserved), pct: (s.reserved_pct || 0).toFixed(1) + "%" },
            { label: "Available", color: COLORS.limit, amount: this.formatCurrency(s.remaining), pct: (s.available_pct || 0).toFixed(1) + "%" },
            { label: "Forecast", color: COLORS.forecast, amount: this.formatCurrency(s.forecast), pct: (s.forecast_pct || 0).toFixed(1) + "%" },
        ];
    }

    formatCurrency(value) {
        const amount = value || 0;
        const text = new Intl.NumberFormat("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Math.abs(amount));
        return (amount < 0 ? "-THB " : "THB ") + text;
    }

    formatStamp(value) {
        // Server value is UTC "YYYY-MM-DD HH:MM:SS"; show in browser local time.
        if (!value) return "";
        const date = new Date(value.replace(" ", "T") + "Z");
        if (isNaN(date)) return value;
        return date.toLocaleString("en-GB", {
            day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
        });
    }

    // ------------------------------------------------------------------
    // Excel export (click a month / week payment point)
    // ------------------------------------------------------------------
    /** scope: "filter" (dashboard company filter), "all", or a company id. */
    async exportPayments(dateFrom, dateTo, scope = "filter") {
        const data = { date_from: dateFrom, date_to: dateTo };
        const companyId = scope === "filter" ? this.state.selectedCompanyId : scope;
        if (companyId && companyId !== "all") {
            data.company_id = companyId;
        }
        try {
            await download({ url: "/budget/api/payments_export", data });
        } catch (error) {
            console.error("Payment export failed", error);
            this.notification.add("Export payments failed", { type: "danger" });
        }
    }

    onPaymentBarClick(index, scope) {
        const row = this.state.payments[index];
        if (!row) return;
        const pad = (n) => String(n).padStart(2, "0");
        const last = new Date(row.year, row.month, 0).getDate();
        return this.exportPayments(
            row.year + "-" + pad(row.month) + "-01",
            row.year + "-" + pad(row.month) + "-" + pad(last),
            scope
        );
    }

    onWeeklyPointClick(datasetIndex, index) {
        const week = this.state.weekly[index];
        // Dataset 3 is the Actual Payment line.
        if (!week || datasetIndex !== 3) return;
        this.exportPayments(week.date_from, week.date_to);
    }

    // ------------------------------------------------------------------
    // Charts
    // ------------------------------------------------------------------
    renderAll() {
        this.renderDepartmentChart();
        this.renderWeeklyChart();
        this.renderPaymentCharts();
    }

    _draw(name, rows, config) {
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
        if (!rows.length) return;
        this.charts[name] = new ChartJS(el.getContext("2d"), config);
    }

    _moneyTooltip() {
        return {
            mode: "index",
            intersect: false,
            callbacks: {
                label: (ctx) => " " + ctx.dataset.label + ": " + this.formatCurrency(ctx.parsed.y),
            },
        };
    }

    _legendOptions() {
        return { position: "top", labels: { usePointStyle: true, padding: 16 } };
    }

    renderDepartmentChart() {
        const rows = this.state.departments;
        const bar = (label, key, color) => ({
            label, data: rows.map((d) => d[key]), backgroundColor: color, borderRadius: 3,
        });
        this._draw("department", rows, {
            type: "bar",
            data: {
                labels: rows.map((d) => d.name),
                datasets: [
                    bar("Limit", "limit", COLORS.limit),
                    bar("Used", "used", COLORS.used),
                    bar("Reserved", "reserved", COLORS.reserved),
                    bar("Forecast", "forecast", COLORS.forecast),
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, ticks: { callback: (v) => v.toLocaleString() } },
                    x: { grid: { display: false }, ticks: { maxRotation: 45, minRotation: 45 } },
                },
                plugins: { legend: this._legendOptions(), tooltip: this._moneyTooltip() },
            },
        });
    }

    renderWeeklyChart() {
        const rows = this.state.weekly;
        const line = (label, key, color, dashed = false) => ({
            label,
            data: rows.map((w) => w[key]),
            borderColor: color,
            backgroundColor: color,
            borderDash: dashed ? [6, 3] : [],
            borderWidth: 2,
            tension: 0.3,
            pointRadius: 3,
            pointHoverRadius: 5,
            fill: false,
        });
        this._draw("weekly", rows, {
            type: "line",
            data: {
                labels: rows.map((w) => [w.label, w.range]),
                datasets: [
                    line("Budgeted Limit", "limit", COLORS.limit, true),
                    line("Reserved (ยอดจอง)", "reserved", COLORS.reserved),
                    line("Actual Used (จ่ายจริง)", "used", COLORS.used),
                    line("Actual Payment (จ่ายจริง)", "payment", COLORS.payment),
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                onClick: (ev, elements, chart) => {
                    const hit = chart.getElementsAtEventForMode(ev, "nearest", { intersect: true }, true)[0];
                    if (hit) this.onWeeklyPointClick(hit.datasetIndex, hit.index);
                },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: compactNumber }, grid: { color: "rgba(0,0,0,0.05)" } },
                    x: { grid: { display: false } },
                },
                plugins: { legend: this._legendOptions(), tooltip: this._moneyTooltip() },
            },
        });
    }

    /**
     * One card per company (plus an all-companies total), built imperatively
     * because the number of companies is dynamic.
     */
    renderPaymentCharts() {
        const grid = this.refs.paymentGrid.el;
        if (!grid) return;
        (this.charts.payments || []).forEach((chart) => chart.destroy());
        this.charts.payments = [];
        grid.replaceChildren();
        const ChartJS = window.Chart;
        const rows = this.state.payments;
        if (!ChartJS || !rows.length) return;

        const series = [{ id: "all", name: "All Companies", color: "#1b2a49" }].concat(
            this.state.paymentCompanies.map((company, i) => ({
                id: company.id,
                name: company.name,
                color: COMPANY_COLORS[i % COMPANY_COLORS.length],
            }))
        );
        for (const item of series) {
            const amounts = rows.map((p) => item.id === "all"
                ? p.amount : ((p.by_company || {})[String(item.id)] || {}).amount || 0);
            const counts = rows.map((p) => item.id === "all"
                ? p.count : ((p.by_company || {})[String(item.id)] || {}).count || 0);
            const total = amounts.reduce((a, b) => a + b, 0);

            const card = document.createElement("div");
            card.className = "o_bd_payment_card";
            const head = document.createElement("div");
            head.className = "o_bd_payment_card_head";
            const name = document.createElement("span");
            name.className = "o_bd_payment_card_name";
            name.textContent = item.name;
            const sum = document.createElement("span");
            sum.className = "o_bd_payment_card_total";
            sum.textContent = this.formatCurrency(total);
            head.append(name, sum);
            const box = document.createElement("div");
            box.className = "o_bd_payment_card_chart";
            const canvas = document.createElement("canvas");
            box.append(canvas);
            card.append(head, box);
            grid.append(card);

            this.charts.payments.push(new ChartJS(canvas.getContext("2d"), {
                data: {
                    labels: rows.map((p) => p.label),
                    datasets: [
                        {
                            type: "bar",
                            label: "Actual Payment",
                            data: amounts,
                            backgroundColor: item.color,
                            borderRadius: 3,
                            yAxisID: "y",
                        },
                        {
                            type: "line",
                            label: "จำนวนรายการจ่าย",
                            data: counts,
                            borderColor: "#10b981",
                            backgroundColor: "#10b981",
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 2,
                            yAxisID: "y1",
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    onClick: (ev, elements, chart) => {
                        const hit = chart.getElementsAtEventForMode(ev, "index", { intersect: false }, true)[0];
                        if (hit) this.onPaymentBarClick(hit.index, item.id);
                    },
                    onHover: (ev, elements) => {
                        ev.native.target.style.cursor = elements.length ? "pointer" : "default";
                    },
                    scales: {
                        y: { beginAtZero: true, position: "left", ticks: { callback: compactNumber }, grid: { color: "rgba(0,0,0,0.05)" } },
                        y1: { beginAtZero: true, position: "right", grid: { drawOnChartArea: false }, ticks: { precision: 0 } },
                        x: { grid: { display: false } },
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => ctx.dataset.yAxisID === "y1"
                                    ? " " + ctx.dataset.label + ": " + ctx.parsed.y
                                    : " " + ctx.dataset.label + ": " + this.formatCurrency(ctx.parsed.y),
                            },
                        },
                    },
                },
            }));
        }
    }
}

WeeklyBudgetDashboard.template = "biz_weekly_budget.WeeklyBudgetDashboard";

registry.category("actions").add("weekly_budget_dashboard", WeeklyBudgetDashboard);
