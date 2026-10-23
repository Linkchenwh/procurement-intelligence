from pathlib import Path

import pytest

from src import data_loader


def test_detects_csv_in_extracted_archive_subfolder(tmp_path, monkeypatch):
    monkeypatch.setattr(data_loader, "ROOT", tmp_path)
    folder = tmp_path / "data/raw/kaggle/archive"
    folder.mkdir(parents=True)
    path = folder / "Procurement KPI Analysis Dataset.csv"
    path.write_text("PO_ID\nTEST\n")
    assert data_loader.performance_path() == path


def test_multiple_csv_candidates_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(data_loader, "ROOT", tmp_path)
    folder = tmp_path / "data/raw/kaggle/archive"
    folder.mkdir(parents=True)
    (folder / "one.csv").write_text("a\n1\n")
    (folder / "two.csv").write_text("a\n2\n")
    with pytest.raises(ValueError, match="多个 CSV"):
        data_loader.performance_path()
