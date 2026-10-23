# 验证说明

## 代码与数据

- 50项pytest覆盖金额状态、NULL、异常输入、SQL/Python一致性、评分方向与敏感性、上传读取和页面集成。
- 无原始下载文件和缓存的干净副本同样通过50项测试。
- 政府保留335,550条观测，198,343个精确订单组合，金额150,481,847,241.30。
- 绩效777行，714条非取消，25个供应商×品类组逐值核对周期、有效分母和合规标签。

## Power BI

2026-10-23版面更新：三页改用1440×960画布，统一中文显示名、字号、表格列宽及下拉筛选。模型定义、字段绑定、Top10金额降序和空月份排除规则保持原样；本次新布局尚未完成Desktop实际渲染与交互复核。仓库图片保留上一版已验证的原生截图，不能据此认为新布局已经验收。

指标基线在Desktop 2.159.883.0实际打开与刷新验证，10表、26度量、6关系；33项DAX数值、25个分组及Top10十个键和金额与Python一致。Top10合计62,612,946,084.69。品类/供应商/品牌交互、未知值和保存关闭重开刷新已核对，三张实际页面截图保存在dashboard/screenshots。

基线截图中的表格、切片器和趋势支持滚动，只显示当前可视部分；精确值以DAX和CSV为准。无承诺交期不计算准时率，无收货分母不发布正式缺陷率；未知税运费等使正式总成本保持BLANK。

公开版使用ProjectRoot参数替代机器目录，参数由prepare_powerbi写入。Power BI定义使用微软TMDL序列化器解析检查；在新电脑上仍需恢复数据并实际刷新。部分Desktop视觉schema版本不可获取，未将其标记为全部通过。

## 复核命令

```powershell
python -m pytest -q
.\scripts\query_powerbi.ps1 -QueryFile dashboard/dax/validation_totals.dax -OutputFile outputs/tables/powerbi_dax_totals.json
.\scripts\query_powerbi.ps1 -QueryFile dashboard/dax/validation_supplier.dax -OutputFile outputs/tables/powerbi_dax_supplier.json
.\scripts\query_powerbi.ps1 -QueryFile dashboard/dax/validation_top10.dax -OutputFile outputs/tables/powerbi_dax_top10.json
```

本仓库用于分析方法与本地工具展示，不声称真实企业采用或已实现节约。数据获取、指标适用范围和缺口分别见数据来源、KPI口径与分析报告。
