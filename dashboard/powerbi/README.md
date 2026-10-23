# Power BI模型

原生项目为ProcurementIntelligence.pbip，包含采购支出总览、供应商绩效、市场对标与寻源三页。金额和订单指标按当前筛选上下文计算，未知值保持BLANK。

当前版面使用中文表头、下拉筛选和1440×960画布；仅调整展示格式，模型与筛选口径未改。新布局尚待Desktop实际复核，README截图仍为此前已验证的基线版本。

| 维表 | 事实表 | 关联键 |
|---|---|---|
| GovSupplier | GovFact | supplier_key |
| GovDepartment | GovFact | department |
| GovType | GovFact | acquisition_type |
| GovDate | GovFact | date → purchase_date |
| PerfSupplier | PerfFact | Supplier |
| PerfCategory | PerfFact | Item_Category |

六条关系均为维表到事实表的单向一对多。MarketQuotes与固定100包情景MarketScenario独立展示，不随意与历史采购关联。

## 首次刷新

1. 按项目运行说明恢复数据，运行 `python -m scripts.run_analysis` 和 `python -m scripts.prepare_powerbi`。
2. prepare_powerbi将本地项目目录写入ProjectRoot参数，保留金额、日期、编码和NULL类型。
3. 打开PBIP，在Desktop执行刷新。也可在Power Query管理参数中修改ProjectRoot。仓库不包含本机缓存。
4. 核对总览金额150,481,847,241.30，绩效714单/10.52天/87.7%/82.4%，市场7条/23.00/32.50及总成本空白。

GovFact.order_id为精确订单组合键的快照整数编码，避免文本大小写比较合并24个订单身份。原始order_key保留；整数ID不是跨版本稳定业务主键。

总览趋势只在该视觉对象排除空月份，日期覆盖约29.6%的金额；Top10按Gov Observed Amount选取并降序，总计62,612,946,084.69。UNKNOWN是未识别桶，不是一家真实供应商。

绩效页底部数字为全量数据基线；上方卡片和表格随品类/供应商筛选变化。市场情景是独立固定100包计算，动态参数调整使用Streamlit。

## DAX核对

只打开目标项目后，可通过scripts/query_powerbi.ps1执行dashboard/dax中的EVALUATE查询，输出到outputs/tables。该工具仅用于Windows Desktop本地只读查询。结果与Python控制表核对的方法和已验证指标见[验证说明](../../docs/validation.md)。

build_powerbi_project用于重新生成定义，运行前关闭该项目。重建后仍需Desktop实际打开和刷新验证。部分Desktop版本的公开视觉JSON schema可能尚未提供，结构校验不能替代实际运行。

仅重新应用版面格式时，可在项目关闭后运行 `python -m scripts.style_powerbi_report dashboard/powerbi/ProcurementIntelligence.Report/definition`；该脚本不修改模型度量、关系、绑定字段或筛选规则。
