# 数据字典

原始CSV保留原名和原值；缺失统一作为null处理，不把未知当0。

## 采购绩效实际CSV与输入契约（每订单一行）

| 字段 | 类型/单位 | 含义与规则 |
|---|---|---|
| PO_ID | 文本，唯一 | 订单标识；重复直接报错，不擅自去重 |
| Supplier | 文本 | 原供应商标签；去首尾空格，保留大小写，不推断法人 |
| Order_Date | 日期 | 下单日期，必填 |
| Delivery_Date | 可空日期 | 页面称交付日期；负周期/无效日期不进入周期均值 |
| Item_Category | 文本 | 品类；不能证明具体商品相同 |
| Order_Status | 枚举 | Delivered/Pending/Cancelled/Partially Delivered |
| Quantity | 正整数 | 模板约定订购数量，不能自动当收货量 |
| Unit_Price | 非负数，币种未知 | 原始单价，不自动视为有效合同基准 |
| Negotiated_Price | 非负数，币种未知 | 议价单价，订单金额=数量×该值 |
| Defective_Units | 可空整数 | 页面称交付后缺陷数量；限定已交付且0≤缺陷≤采购量，未知分母不出正式缺陷率 |
| Compliance | 可空记录 | Yes/No及明确同义标签；无法识别保留未知 |
| amount / baseline_amount | 派生数值 | 议价后/原价订单金额 |
| valid_order / delivered_order | 布尔 | 分别为非取消/Delivered，不代表付款有效性 |
| delivery_days | 可空天数 | 只用Delivered且日期非负；缺失不填0 |
| compliant | 可空0/1 | 对明确合规标签编码；均值分母为已知记录数 |

实际CSV已审计：777行、上述11个原字段，PO_ID唯一，无完全重复；5供应商、5品类。Delivered 560、Pending 81、Partially Delivered 73、Cancelled 63。Delivery_Date缺87，Defective_Units缺136，其余原字段无缺失。字段定义参考此前Kaggle页面，记录一致性问题见[异常审计](../outputs/tables/performance_audit.json)。

供应商派生表每Supplier×Item_Category一行，共25组；orders仅非取消订单。delivered_orders为已交付数，delivery_coverage=有效周期样本/已交付数，quality_record_coverage=有有效缺陷数量的已交付样本/已交付数，分母为0时为空。watch_notes只记录缺口与No标记。performance_supplier_overall.csv共5行，Item_Category标记ALL_CATEGORIES_DESCRIPTIVE_ONLY，禁止送入评分。performance_record_issues.csv的source_record为CSV记录序号+2，不保证等于物理文本行号，issue_codes可多值。

performance_scoring_hypotheses.csv每品类×供应商×权重情景一行，共75行，包含comparability_assumption及各维度权重；不是已验证业务条件的正式采购排名。

## 加州原始字段（每行是来源观察，官方唯一行键缺失）

| 字段组 | 实际字段 | 用途与限制 |
|---|---|---|
| 日期 | Creation Date、Purchase Date、Fiscal Year | 创建≠采购；采购日期只在报告财年内进入趋势，不修正错误年份 |
| 订单 | Purchase Order Number、Requisition Number、LPA Number | 订单组合键=部门+财年+订单号，是分析约定，不能保证官方全局唯一 |
| 部门/方式 | Department Name、Acquisition Type、Sub-Acquisition Type、Acquisition Method、Sub-Acquisition Method、CalCard | 主分类用Acquisition Type，避免一行扩展多个商品分类 |
| 供应商 | Supplier Code、Supplier Name、Supplier Qualifications、Supplier Zip Code | 按编码聚合；名称变体不自动合并；资格字段不是全面合规审计 |
| 物品 | Item Name、Item Description、Quantity、Unit Price、Total Price | $/逗号/括号负数解析；Total Price作为行额，经数量×单价核对，容差0.02 |
| 分类 | Classification Codes、Normalized UNSPSC、Commodity Title、Class、Class Title、Family、Family Title、Segment、Segment Title | 可能分类展开；不把重复观察重复计额；多品类订单数不可跨组直接求和 |
| 其他 | Location、REMOVE AMERISOURCE | 地理字段不进入业务建模；最后字段原数据全空，保留审计而不分析 |

实际32个字段的完整非空/基数统计见 `outputs/tables/government_field_audit.csv`。
PDF字典涵盖Fi$Cal新模式，包含LineNumber/GrandTotal等字段，本CSV没有这些字段，不能假装能按官方行号去重。

派生 `source_row` 是CSV记录序号+2，不是物理文本行号（CSV内部可能换行）。`supplier_key`来自编码，缺失或来源编码0且名称Unknown时归到UNKNOWN单独一桶，不当成一家已知供应商。`order_key`字段间用␟分隔。BI导出的`order_id`是精确order_key字符串的整数编码，仅当前快照内有效；DAX对其计数，避免文本大小写规则合并24个身份。`purchase_date`是通过财年一致性检查后的日期。`exclusion_reason`保留隔离原因。

## 市场报价（每商品、渠道、观察时点一条报价）

| 字段 | 类型 | 含义 |
|---|---|---|
| quote_id、sku | 文本 | 快照内唯一观察ID、商家货号/可识别型号 |
| brand、manufacturer、seller、contract_supplier、channel | 文本 | 品牌/生产商/销售商/合同方/渠道分开 |
| product_name、attributes | 文本 | 商品自身h1和属性；不用推荐商品内容补参数 |
| paper_size、gsm、sheets_per_ream、reams_per_box | 文本/数值 | A4、80g/m²、500张/包、每箱包数；不完整则不强行比较 |
| price、currency、quote_unit | 数值/文本 | 原标价、ISO币种、ream或box |
| min_order_units、max_order_units | 可空整数 | 已核实起订销售单位数、该标价适用数量上限；输入框默认1不是MOQ证明 |
| tax_status、tax_terms | 枚举/文本 | included/excluded/unknown；有发票不证明标价含税 |
| shipping_cost、shipping_terms、region | 可空数值/文本 | 对本次目标数量和地区核实的运费；未知不填0 |
| lead_time_days | 可空非负数 | 已核实目标地区交期 |
| collected_at、url | 时间/链接 | 采集时间和原始商品链接 |
| data_status、notes、review_note | 文本 | observed_public_page/needs_review等，保留异常 |
| evidence_file、evidence_sha256 | 本地相对路径/哈希 | 本地复核，不默认公开HTML |
| packaging_conflict | 布尔 | 标题/属性不一致时排除规格比较 |
| price_per_500 | 派生数值 | price÷(每计价单位包数×每包张数)×500；只有已核实基础规格可比时保留 |

市场上传只做格式验证，统一标记user_uploaded_unverified，不自动获得外部来源真实性认证。
