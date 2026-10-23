"""Format native report pages without changing data bindings or measures."""
import json
from pathlib import Path


def literal(value):
    return {'expr': {'Literal': {'Value': value}}}


def properties(**values):
    return [{'properties': {key: literal(value) for key, value in values.items()}}]


DISPLAY_NAMES = {
    'supplier_key': '供应商编码', 'supplier_label': '供应商名称',
    'fiscal_year': '财年', 'department': '部门', 'acquisition_type': '采购类型', 'month': '月份',
    'Gov Observed Amount': '保留观测金额', 'Gov Observed Orders': '订单组合数',
    'Gov Known Suppliers': '已知供应商编码数', 'Gov Top5 Share': 'Top5金额占比',
    'Supplier': '供应商', 'Item_Category': '品类',
    'Perf Noncancelled Orders': '非取消订单', 'Perf Delivered Orders': '已交付订单',
    'Perf Delivery Samples': '有效周期样本', 'Perf Delivery Days': '平均周期（天）',
    'Perf Delivery Coverage': '周期覆盖率', 'Perf Recorded Compliance Rate': '合规标签Yes率',
    'Perf Compliance Samples': '合规样本', 'Perf Quality Samples': '缺陷记录样本',
    'Perf Quality Record Coverage': '缺陷记录覆盖率',
    'brand': '品牌', 'currency': '币种', 'product_name': '商品', 'price_per_500': '标价/500张',
    'spec_comparable': '规格可比', 'collected_at': '采集时间', 'url': '来源链接',
    'requested_reams': '需求（包）', 'purchase_units': '采购单位数',
    'goods_reference_cost': '货品参考金额', 'total_cost': '到货总成本',
    'budget_difference': '预算差额', 'limitations': '待核实条件',
    'Market Comparable Listed Price': '标价/500张',
}

TITLES = {
    'spend_card_0': '保留观测金额（十亿，原币）', 'spend_card_1': '订单组合数',
    'spend_card_2': '已知供应商编码数', 'spend_card_3': 'Top5金额占比',
    'spend_year': '财年筛选', 'spend_department': '部门筛选',
    'spend_type': '采购类型金额', 'spend_trend': '月度金额（有效日期覆盖约29.6%）',
    'spend_supplier': '供应商金额 Top10（UNKNOWN为未识别桶）',
    'perf_card_0': '非取消订单', 'perf_card_1': '平均交付周期（天）',
    'perf_card_2': '有效周期记录覆盖率', 'perf_card_3': '已知合规标签Yes率',
    'perf_category': '品类筛选', 'perf_supplier_filter': '供应商筛选',
    'perf_table': '供应商观测指标与有效样本',
    'perf_cycle': '交付周期均值（仅日期有效样本）', 'perf_compliance': '已知合规标签中的Yes占比',
    'market_card_0': '基础规格可比记录', 'market_card_1': '最低标价（同币种/500张）',
    'market_card_2': '最高标价（同币种/500张）', 'market_card_3': '到货总成本（条件待核实）',
    'market_brand': '品牌筛选', 'market_currency': '币种筛选',
    'market_price': '同规格公开标价（单一渠道）', 'market_evidence': '来源与规格可比性',
    'market_scenario': '固定100包情景：货品参考金额与到货总成本分列',
}

TEXT = {
    'spend_heading': '采购支出总览：加州历史观测',
    'spend_scope': '2012–2015财年；保留335,550条历史观测，金额不等于付款。日期有效部分用于月度趋势。',
    'spend_footer': '来源：California DGS历史开放数据；异常与疑似重复已隔离，不代表全州完整采购支出。\n集中度描述当前观测组合；原始金额口径、日期覆盖与限制见分析报告。三个数据域独立。',
    'perf_heading': '供应商绩效：公开订单练习',
    'perf_scope': '全量范围：777条订单、5家供应商、5个品类；下方指标随当前筛选变化，跨品类仅作描述。',
    'perf_footer': '全量数据基线：有效周期491/560；68条已交付缺日期、1条先后异常。记录覆盖不等于准时率或合格率。\n企业来源未独立验证、币种未知；同品类仍需核实业务可比性，无收货分母不发布正式缺陷率，名义价差不称已实现节约。',
    'market_heading': '市场对标与寻源：A4 / 80g / 500张',
    'market_scope': '2026-10-22单渠道公开标价快照；非有效询价或成交价，品牌不等于生产商或合同主体。',
    'market_footer': '税运费、MOQ、数量区间与地区条件未知时，到货总成本保持空白；不同币种不能直接比较。\n固定100包情景独立于品牌/币种筛选；动态数量在Streamlit调整后导出再刷新，完整来源与待核实条件见数据表。',
}

BOXES = {
    'spend_year': (32, 228, 400, 78), 'spend_department': (468, 228, 940, 78),
    'spend_type': (32, 324, 620, 228), 'spend_trend': (688, 324, 720, 228),
    'spend_supplier': (32, 576, 1376, 304),
    'perf_category': (32, 228, 660, 78), 'perf_supplier_filter': (728, 228, 680, 78),
    'perf_table': (32, 324, 1376, 236), 'perf_cycle': (32, 584, 660, 284),
    'perf_compliance': (728, 584, 680, 284),
    'market_brand': (32, 228, 660, 78), 'market_currency': (728, 228, 680, 78),
    'market_price': (32, 324, 660, 308), 'market_evidence': (728, 324, 680, 308),
    'market_scenario': (32, 652, 1376, 232),
}

COLUMN_WIDTHS = {
    'spend_supplier': [130, 930, 300],
    'perf_table': [150, 115, 115, 125, 130, 120, 140, 110, 130, 150],
    'market_evidence': [92, 100, 62, 80, 238, 76],
    'market_scenario': [360, 90, 110, 150, 130, 110, 390],
}


def query_bindings(visual):
    query = json.loads(json.dumps(visual.get('query', {})))
    for state in query.get('queryState', {}).values():
        for projection in state.get('projections', []):
            projection.pop('displayName', None)
            projection.pop('format', None)
    return query


def style_report(report_definition):
    report_definition = Path(report_definition)
    changed = 0
    for page in ['spend_overview', 'supplier_performance', 'market_sourcing']:
        page_root = report_definition / 'pages' / page
        page_file = page_root / 'page.json'
        page_config = json.loads(page_file.read_text(encoding='utf-8-sig'))
        page_config.update(width=1440, height=960, displayOption='FitToPage')
        page_file.write_text(json.dumps(page_config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        for file in (page_root / 'visuals').glob('*/visual.json'):
            config = json.loads(file.read_text(encoding='utf-8-sig'))
            name = config['name']
            visual = config['visual']
            before_query = query_bindings(visual)
            before_filters = json.loads(json.dumps(config.get('filterConfig')))
            if name.endswith('_heading'):
                box = (32, 16, 1376, 42)
            elif name.endswith('_scope'):
                box = (32, 66, 1376, 40)
            elif '_card_' in name:
                box = (32 + int(name[-1]) * 348, 116, 328, 96)
            elif name.endswith('_footer'):
                box = (32, 898, 1376, 58)
            else:
                box = BOXES[name]
            x, y, width, height = box
            assert x >= 0 and y >= 0 and x + width <= 1440 and y + height <= 960
            config['position'].update(x=x, y=y, width=width, height=height)
            container = visual.setdefault('visualContainerObjects', {})
            container['subTitle'] = properties(show='false')
            if 'title' in container:
                title = container['title'][0]['properties']
                title.update(fontFamily=literal("'SimSun'"), fontSize=literal('13D'))
                if name in TITLES:
                    title['text'] = literal("'" + TITLES[name] + "'")
            for state in visual.get('query', {}).get('queryState', {}).values():
                for projection in state.get('projections', []):
                    field_name = projection.get('nativeQueryRef')
                    if field_name in DISPLAY_NAMES:
                        projection['displayName'] = DISPLAY_NAMES[field_name]
                    if name == 'spend_card_0':
                        projection['format'] = '#,0.00,,,'
            objects = visual.setdefault('objects', {})
            kind = visual['visualType']
            if kind == 'textbox':
                paragraph = objects['general'][0]['properties']['paragraphs'][0]
                paragraph['textRuns'] = [{'value': TEXT[name], 'textStyle': {
                    'fontFamily': 'SimSun', 'fontSize': '24pt' if name.endswith('_heading') else ('11pt' if name.endswith('_footer') else '12pt'),
                }}]
            elif kind == 'card':
                objects['labels'][0]['properties'].update(fontFamily=literal("'Arial'"), fontSize=literal('30D'), labelDisplayUnits=literal('1D'))
            elif kind == 'slicer':
                objects['data'] = properties(mode="'Dropdown'")
                objects['header'] = properties(show='false')
                objects['items'] = properties(fontFamily="'SimSun'", textSize='12D')
            elif kind == 'tableEx':
                size = '10D' if name.startswith('market_') else '11D'
                objects['columnHeaders'] = properties(fontFamily="'SimSun'", fontSize=size, wordWrap='true', autoSizeColumnWidth='false')
                objects['values'] = properties(fontFamily="'Arial'", fontSize=size, wordWrap='false', urlIcon='true')
                objects['total'] = properties(fontFamily="'Arial'", fontSize=size)
                objects['grid'] = properties(rowPadding='0D', gridHorizontal='false', gridVertical='false')
                projections = visual['query']['queryState']['Values']['projections']
                assert len(projections) == len(COLUMN_WIDTHS[name])
                objects['columnWidth'] = [{'selector': {'metadata': p['queryRef']}, 'properties': {'value': literal(str(w) + 'D')}} for p, w in zip(projections, COLUMN_WIDTHS[name])]
            elif kind in ['barChart', 'lineChart']:
                objects['categoryAxis'] = properties(show='true', showAxisTitle='false', fontFamily="'Arial'", fontSize='11D')
                objects['valueAxis'] = properties(show='true', showAxisTitle='false', fontFamily="'Arial'", fontSize='11D')
                objects['legend'] = properties(show='false')
                if kind == 'barChart':
                    objects['categoryAxis'][0]['properties']['innerPadding'] = literal('30D')
                if name in ['perf_cycle', 'perf_compliance', 'market_price']:
                    objects['labels'] = properties(show='true', fontFamily="'Arial'", fontSize='11D', labelDisplayUnits='1D', labelPrecision='1D' if name == 'perf_compliance' else '2D')
            assert query_bindings(visual) == before_query, name
            assert config.get('filterConfig') == before_filters, name
            file.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
            changed += 1
    return changed


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('report_definition', type=Path)
    args = parser.parse_args()
    print(f'Formatted {style_report(args.report_definition)} native visuals; Desktop rendering must be checked separately.')
