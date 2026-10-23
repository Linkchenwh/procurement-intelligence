from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from src.data_loader import performance_path

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("page", ["采购经营总览", "供应商评价", "市场价格对标", "综合决策与导出"])
def test_pages_render_without_exception(page):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.sidebar.radio(key="page").set_value(page).run()
    assert len(app.exception) == 0


def test_invalid_weight_prompt_without_crash():
    # Without official practice data, the page must explain the prerequisite instead of using fake data.
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.sidebar.radio(key="page").set_value("供应商评价").run()
    assert len(app.exception) == 0
    if performance_path() is None:
        assert any("Kaggle" in x.value for x in app.info)
    else:
        app.checkbox(key="confirm_comparable").check().run()
        app.number_input(key="delivery_weight").set_value(0)
        app.number_input(key="compliance_weight").set_value(0).run()
        assert any("权重" in x.value for x in app.error)
        assert len(app.exception) == 0
