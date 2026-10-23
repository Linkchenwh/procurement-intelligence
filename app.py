"""Local procurement portfolio. No production data are replaced by synthetic samples."""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_cleaning import clean_performance
from src.data_loader import ROOT, read_table, performance_path
from src.export_utils import csv_bytes
from src.government import government_summary, government_breakdown
from src.market_benchmark import normalize_quotes
from src.scenario_analysis import sourcing_scenario
from src.scoring_model import score_suppliers, sensitivity
from src.spend_analysis import spend_summary, spend_breakdown, monthly_spend
from src.supplier_analysis import supplier_metrics

st.set_page_config(page_title="采购分析与寻源决策", layout="wide")
st.title("采购分析与寻源决策")
st.caption("个人作品集 · 公开练习 / 政府历史采购 / 市场标价三个独立案例")
page = st.sidebar.radio("功能页面", ["采购经营总览", "供应商评价", "市场价格对标", "综合决策与导出"], key="page")
perf_upload = st.sidebar.file_uploader("采购绩效表（CSV/XLSX）", type=["csv", "xlsx"], key="performance_upload")
market_upload = st.sidebar.file_uploader("市场报价表（CSV/XLSX）", type=["csv", "xlsx"], key="market_upload")
st.sidebar.caption("上传文件仅在当前会话内处理。用户数据的业务真实性需另行核验。")
for template, label in [("performance_input.csv", "下载采购输入模板"), ("market_quotes_input.csv", "下载报价采集模板")]:
    path = ROOT / "data/templates" / template
    if path.exists():
        st.sidebar.download_button(label, path.read_bytes(), template, mime="text/csv", key=template)


@st.cache_data(show_spinner=False)
def read_processed(path, modified):
    return pd.read_parquet(path)


def processed(name):
    path = ROOT / "data/processed" / (name + ".parquet")
    return read_processed(str(path), path.stat().st_mtime_ns) if path.exists() else None


def performance_data():
    if perf_upload is not None:
        st.caption("当前来源：用户上传的采购练习格式数据；币种/企业真实性未验证。")
        return clean_performance(read_table(perf_upload))[0]
    path = performance_path()
    if path is None:
        st.info("需要 Kaggle 正式 CSV 或符合模板的上传文件。下载后放入 data/raw/kaggle，再运行分析脚本。")
        return None
    st.caption("当前来源：本地Kaggle公开练习CSV；作者的企业来源声明未独立验证，币种未知。")
    return clean_performance(read_table(path))[0]


def market_data():
    if market_upload is not None:
        st.caption("当前来源：用户上传报价；系统只核验格式，不自动证明价格真实。")
        raw = read_table(market_upload)
        # Uploaded source assertions alone do not establish external verification.
        raw["data_status"] = "user_uploaded_unverified"
        return normalize_quotes(raw)
    path = ROOT / "data/market/quotes_reviewed.csv"
    if not path.exists():
        path = ROOT / "data/market/quotes.csv"
    if not path.exists():
        st.info("尚无市场报价。可下载采集模板后上传真实观察记录。")
        return None
    return normalize_quotes(pd.read_csv(path))


def chart(frame, x, y, title):
    if frame.empty:
        st.info("筛选后无记录")
        return
    fig = px.bar(frame, x=y, y=x, orientation="h", title=title)
    fig.update_layout(font_family="Arial, SimSun", showlegend=False, height=max(320, len(frame) * 38 + 120),
                      margin=dict(t=60, b=50, l=240), xaxis_title=y, yaxis_title=None)
    fig.update_yaxes(autorange="reversed", automargin=True)
    st.plotly_chart(fig, width="stretch")


def download(frame, name, key):
    st.download_button("下载当前结果 CSV", csv_bytes(frame), name, "text/csv", key=key)


def trend_chart(frame):
    if frame.empty:
        st.info("当前筛选没有有效日期，无法显示趋势")
        return
    fig = px.line(frame, x="month", y="amount", title="有效采购日期范围内的月度观测金额")
    fig.update_layout(font_family="Arial, SimSun", xaxis_title="采购月份", yaxis_title="来源金额")
    st.plotly_chart(fig, width="stretch")


def overview():
    domain = st.selectbox("独立分析数据域", ["加州历史采购（观测子集）", "采购绩效练习"], key="overview_domain")
    if domain.startswith("加州"):
        data = processed("government")
        st.warning("2012–2015财年历史记录；当前展示排除疑似重复和数值异常后的观测子集。金额不是全州完整支出或付款。源文件$按语境推断为USD。")
        if data is None:
            st.info("先获取政府原始CSV并执行 python -m scripts.run_analysis。")
            return
        years = st.multiselect("财年", sorted(data["Fiscal Year"].unique()), default=sorted(data["Fiscal Year"].unique()))
        categories = st.multiselect("采购类型", sorted(data["Acquisition Type"].dropna().unique()))
        departments = st.multiselect("部门", sorted(data["Department Name"].dropna().unique()))
        data = data.loc[data["Fiscal Year"].isin(years)]
        if categories:
            data = data.loc[data["Acquisition Type"].isin(categories)]
        if departments:
            data = data.loc[data["Department Name"].isin(departments)]
        if data.empty:
            st.info("筛选后无记录")
            return
        result = government_summary(data)
        columns = st.columns(4)
        for col, label, value in zip(columns, ["观测金额（十亿源币）", "涉及订单组合", "已知供应商编码", "Top5占比"],
                [f"{result['amount']/1e9:,.3f}", f"{result['orders']:,}", f"{result['supplier_codes']:,}", f"{result['top5_share']:.1%}"]):
            col.metric(label, value)
        st.caption(f"源文件金额精确到分：{result['amount']:,.2f}；未识别供应商桶金额 {result['unknown_supplier_amount']:,.2f}，不是一家真实供应商。")
        table = government_breakdown(data, "supplier_key")
        names = data.groupby("supplier_key").supplier_label.first()
        table["供应商"] = table.supplier_key.map(names)
        chart(table.head(10), "供应商", "amount", "Top10供应商编码金额（当前观测子集）")
        category = government_breakdown(data, "Acquisition Type")
        chart(category, "Acquisition Type", "amount", "采购类型结构")
        trend = data.dropna(subset=["purchase_date"]).copy()
        trend["month"] = trend.purchase_date.dt.to_period("M").astype(str)
        trend = trend.groupby("month", as_index=False).amount.sum()
        trend_chart(trend)
        dated_amount = data.loc[data.purchase_date.notna(), "amount"].sum()
        coverage = dated_amount / result['amount'] if result['amount'] > 0 else 0
        st.caption(f"月度趋势排除缺失或与财年不一致的日期，覆盖当前金额的{coverage:.1%}。HHI={result['hhi']:.2f}，只描述当前筛选观测集。")
        st.dataframe(table.head(100), hide_index=True)
        table["amount_scope"] = "accepted_observation_subset_not_statewide_total"
        download(table, "government_supplier_current_scope.csv", "government_export")
        with st.expander("数据审计与覆盖范围"):
            audit = ROOT / "outputs/tables/government_audit.json"
            if audit.exists():
                st.json(json.loads(audit.read_text(encoding="utf-8")))
    else:
        st.caption("公开采购练习数据；作者声称匿名企业来源，真实性未独立验证，币种未知。")
        data = performance_data()
        if data is None:
            return
        categories = st.multiselect("品类筛选", sorted(data.Item_Category.unique()))
        suppliers = st.multiselect("供应商筛选", sorted(data.Supplier.unique()))
        dates = st.date_input("订单日期范围", (data.Order_Date.min().date(), data.Order_Date.max().date()))
        if categories:
            data = data.loc[data.Item_Category.isin(categories)]
        if suppliers:
            data = data.loc[data.Supplier.isin(suppliers)]
        if isinstance(dates, (tuple, list)) and len(dates) == 2:
            data = data.loc[data.Order_Date.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]) + pd.Timedelta(days=1), inclusive="left")]
        if data.empty:
            st.info("筛选后无记录")
            return
        result = spend_summary(data)
        st.json(result)
        st.caption("valid_amount 为非取消订单金额，含未交付；nominal_price_difference 仅为名义议价差额。")
        chart(spend_breakdown(data, "Item_Category"), "Item_Category", "amount", "非取消订单金额：品类")
        st.dataframe(spend_breakdown(data, "Supplier"), hide_index=True)
        trend_chart(monthly_spend(data))
        download(pd.DataFrame([result]), "performance_kpis.csv", "performance_export")


def supplier_page():
    st.subheader("供应商评价：采购绩效练习数据")
    data = performance_data()
    if data is None:
        return
    category = st.selectbox("评价品类", sorted(data.Item_Category.unique()), key="supplier_category")
    assumption = st.checkbox("仅用于假设演示：已交付订单采购数量等于收货数量", value=False)
    metrics = supplier_metrics(data, category, ordered_equals_received=assumption)
    st.dataframe(metrics, hide_index=True)
    st.caption("交付周期仅计算已交付且日期有效订单。没有承诺交期，不计算准时率；缺陷率默认不可用。")
    st.caption("delivery_coverage=有效周期记录/已交付订单；quality_record_coverage=有缺陷记录的已交付订单/已交付订单，均不是准时率或合格率。watch_notes仅为数据观察。")
    download(metrics, "supplier_observed_metrics.csv", "supplier_metrics_export")
    if metrics.empty:
        return
    candidates = st.multiselect("候选供应商", metrics.Supplier.tolist(), default=metrics.Supplier.tolist())
    metrics = metrics.loc[metrics.Supplier.isin(candidates)]
    confirmed = st.checkbox("确认本次候选队列具有可比业务条件，仅作探索性评分", value=False, key="confirm_comparable")
    a, b, c = st.columns(3)
    delivery = a.number_input("周期权重", min_value=0, max_value=100, value=50, key="delivery_weight")
    compliance = b.number_input("合规记录权重", min_value=0, max_value=100, value=50, key="compliance_weight")
    quality = c.number_input("缺陷率假设权重", min_value=0, max_value=100, value=0, disabled=not assumption)
    min_samples = st.number_input("每个参与维度最少样本数", min_value=1, value=5)
    gate = st.slider("合规记录准入门槛", 0., 1., 0., .05)
    if not confirmed:
        st.info("品类相同不自动证明商品或交付条件可比。确认比较条件后才显示探索性排序。成本维度因缺商品规格而不评分。")
        return
    weights = {"delivery_days": delivery, "compliance_rate": compliance}
    if assumption:
        weights["defect_rate_proxy"] = quality
    result = score_suppliers(metrics, weights, comparable=True, min_samples=min_samples, min_compliance=gate)
    st.dataframe(result, hide_index=True)
    st.caption("权重按输入比例归一化至100%。缺失不填最佳/最差；相同表现记50分。候选集变化会改变min-max分数。")
    scenarios = {"周期优先": {"delivery_days": .8, "compliance_rate": .2}, "合规优先": {"delivery_days": .2, "compliance_rate": .8}}
    st.dataframe(sensitivity(metrics, scenarios, min_samples=min_samples, min_compliance=gate)[["scenario", "Supplier", "score", "rank", "eligibility_note"]], hide_index=True)
    download(result, "supplier_exploratory_scores.csv", "supplier_export")


def market_page(decision=False):
    st.subheader("独立市场案例：A4 / 80g/m² / 500张")
    quotes = market_data()
    if quotes is None or quotes.empty:
        return
    st.warning("公开标价观察，不等于有效询价或成交报价。未知税费、运费、MOQ、数量适用范围不会自动填零。")
    currency = st.selectbox("报价币种", sorted(quotes.currency.dropna().unique()), key="quote_currency")
    brands = st.multiselect("品牌筛选", sorted(quotes.brand.dropna().unique()))
    quotes = quotes.loc[quotes.currency.eq(currency)]
    if brands:
        quotes = quotes.loc[quotes.brand.isin(brands)]
    only_spec = st.checkbox("仅显示基础规格可比记录", value=False)
    if only_spec:
        quotes = quotes.loc[quotes.spec_comparable]
    display_columns = ["brand", "product_name", "price", "quote_unit", "price_per_500", "currency", "spec_comparable", "collected_at", "url", "evidence_note"]
    st.dataframe(quotes[display_columns], hide_index=True)
    comparable = quotes.loc[quotes.spec_comparable]
    if not comparable.empty:
        chart(comparable, "product_name", "price_per_500", f"基础同规格公开标价（{currency}/500张；条件仍待核实）")
    st.subheader("假设采购需求")
    a, b, c = st.columns(3)
    demand = a.number_input("需求包数（500张/包）", min_value=1, value=100)
    budget = b.number_input(f"预算（{currency}）", min_value=0., value=3000.)
    region = c.text_input("目标配送地区", value="深圳")
    delivery_limit = st.number_input("目标交付天数（0表示不筛选）", min_value=0, value=0)
    shipping = st.checkbox("计入已知本情景运费", value=True)
    tax = st.checkbox("仅保留已核实含税报价", value=False)
    result = sourcing_scenario(quotes, demand, budget=budget, currency=currency, region=region,
                               max_lead_days=delivery_limit or None, include_shipping=shipping, only_tax_included=tax)
    if result.empty:
        st.info("当前筛选下没有满足条件的报价。")
        return
    st.dataframe(result[["product_name", "purchase_units", "supplied_reams", "goods_reference_cost", "total_cost", "budget_difference", "rank", "limitations"]], hide_index=True)
    st.caption("参考货品金额按观察标价线性外推；数量阶梯价未核实的情景不会生成总成本/正式排名。")
    if decision:
        st.info("采购动作：补齐统一含税到货报价、MOQ、数量价格区间、库存交期、制造商与合同供应商，再比较总成本。三个数据域不生成联合节约率。")
    download(result, "sourcing_scenario.csv", "scenario_export")
    download(quotes, "normalized_market_quotes.csv", "quotes_export")


try:
    if page == "采购经营总览":
        overview()
    elif page == "供应商评价":
        supplier_page()
    else:
        market_page(decision=page == "综合决策与导出")
except (ValueError, OSError, KeyError, TypeError) as error:
    st.error(f"当前输入无法分析：{error}")
    st.info("请按模板检查字段、日期、数值和数据粒度。原始文件不会被修改。")
