# 数据来源

| 数据域 | 来源 | 使用范围 |
|---|---|---|
| 历史采购 | [California DGS Purchase Order Data](https://data.ca.gov/dataset/purchase-order-data) | 2012–2015财年；来源页注明No Restrictions on Public Use；以实际CSV字段为准 |
| 供应商绩效 | [Kaggle Procurement KPI Analysis Dataset](https://www.kaggle.com/datasets/shahriarkabir/procurement-kpi-analysis-dataset) | 777行、11列；来源页CC0于2026-10-22核查；企业来源声明未独立验证 |
| 市场报价 | [佰欣公开商品目录](https://www.go-easy.com.cn/category-700-b0.html)及商品详情页 | 2026-10-22单渠道标价快照；10条事实摘录，保留URL、时间与证据哈希；不分发整页HTML |

政府原CSV SHA256：`45aa37a683e308c17c28c2edaadf08692be18ed17131afe8edf2e701abc6c9b5`。
绩效原CSV SHA256：`bf9a529c52cd7de254994a55d087f865d3aefc0ba66790e8ee43a26e7beb6e9c`。

## 获取数据

1. 政府：运行 `python scripts/fetch_sources.py california`。下载保存在data/raw/california，脚本保留已有文件并记录来源与哈希。
2. 绩效：从Kaggle页面下载ZIP，将其中CSV解压到data/raw/kaggle或其子目录。程序只接受一个候选CSV，多文件会报错；无需向脚本提供账号令牌。
3. 市场：运行 `python -m scripts.collect_market` 和 `python -m scripts.review_market`。证据HTML只保存本地。新采集是新的观察快照，不能用新页面替代旧快照的历史证据。
4. 依次运行 `python -m scripts.run_analysis`、`python -m scripts.prepare_powerbi`，生成派生数据和看板输入。

仓库提供汇总结果和有限报价事实，不提供原始大文件、网页HTML或下载凭据。原始数据、第三方基础主题和依赖保留各自权利及许可条款。
