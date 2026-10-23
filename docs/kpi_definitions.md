# KPI口径与使用边界

| 中文 / English | 计算、过滤与单位 | 来源/意义/限制 |
|---|---|---|
| 原始订单额 / Raw order value | ΣQuantity×Negotiated_Price，全部状态 | 绩效模板，币种未知；非付款 |
| 非取消订单额 / Noncancelled order value | 上式排除Cancelled | 仍含未交付和部分交付，不称已实现支出 |
| 已交付订单额 / Delivered order value | 上式仅Delivered | 仍不是支付/发票金额 |
| 取消订单额 / Cancelled order value | 上式仅Cancelled | 与非取消额加和等于原始额 |
| 名义议价差额 / Nominal price difference | 非取消ΣQuantity×(Unit_Price−Negotiated_Price) | 没合同/基准不能称实际节约 |
| 订单数量 / Order count | COUNT DISTINCT订单键 | 绩效PO_ID唯一；政府用部门+财年+订单号组合 |
| 供应商数 / Supplier count | 非取消Supplier，或政府已知Supplier Code去重 | 不把UNKNOWN作为已知供应商 |
| 品类/供应商占比 / Spend share | 当前分析范围分组金额÷总金额 | 同分母，同数据域、状态、币种 |
| Top N集中度 / Concentration | 当前范围金额最大N个供应商占比和 | 分母为全部纳入行额，未知供应商单桶单独披露；不是市场份额 |
| HHI | Σ供应商金额占比²×10000 | 描述采购组合集中度，不直接套市场垄断或信用评级阈值 |
| ABC | 金额降序；累计前一项<80%为A、<95%为B，其他C | 阈值是分析规则；跨阈值的当项留前档；零总额不分类 |
| 月度订单额 / Monthly order value | 按有效采购日期分月Σ金额 | 政府异常/缺失日期保留金额但排除趋势；月订单数不可直接加为全期订单数 |
| 采购至实际交付周期 / Delivery cycle | Delivered且日期有效，Delivery−Order的日数均值 | 分母=有效周期记录数；不等于准时率，无承诺日期不计算准时率 |
| 周期记录覆盖 / Delivery record coverage | 有效周期样本数÷Delivered订单数 | 衡量记录可用性，不是准时率；分母0则null |
| 质量记录覆盖 / Quality record coverage | 有有效缺陷数量观测的Delivered记录数÷Delivered订单数 | 衡量记录可用性，不是合格率；分母0则null |
| 合规记录占比 / Recorded compliance share | 明确Yes数÷明确Yes或No数 | 另报有效分母；未知不视合规/违规；不是全面法律合规 |
| 缺陷数量观测 / Observed defects | 有效已交付缺陷数和，全部缺失则null | 交付数量未知，不出正式缺陷率/合格量 |
| 缺陷率假设 / Defect proxy | 用户明确启用采购量=收货量时，Σ同队列缺陷÷Σ同队列采购量 | 探索性假设，不得进正式采购质量报告 |
| 政府观测子集金额 / Accepted observation amount | 通过重复候选组和数值一致性检查的行额和 | 历史观测子集，不是全州完整采购/付款；隔离影响单列 |
| 标准化标价 / Listed price per500 | price÷计价单位总张数×500 | 同A4/80g/500张、无包装冲突；同币种分别比较，不换汇 |
| 参考货品情景金额 / Goods reference scenario | 按包装取整并考虑已知MOQ后的销售单位数×观察标价 | 数量阶梯价未知时只是线性假设，不是大宗有效报价 |
| 已知总成本 / Verified-condition total | 条件齐备的货品金额+本情景已核实运费；含税、地区、MOQ、价格数量上限、有效期/目标交期均符合 | 当前正式报价均条件不足，保持null；不是0 |
| 预算差异 / Budget difference | 预算−条件齐备总成本 | 未知总成本则未知；不输出虚假节约率 |

采购数量在不同商品/计量单位下不汇总为一个业务KPI。绩效模板Quantity可用于单行金额，但品类内也不一定为同一种物品。加州数量含小数，不使用绩效模板的整数约束。

跨品类供应商汇总仅作描述，不参与整体优劣评分。批量评分输出为明确的可比性假设案例：周期/合规权重50/50、80/20、20/80，质量/成本为0，至少5个有效样本；真实SKU、合同与服务条件未经验证。界面探索性评分需要用户显式确认比较条件。
