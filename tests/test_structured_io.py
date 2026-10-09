from __future__ import annotations

from pathlib import Path

import pytest

from harnessbench.grading.structured_io import (
    StructuredDataError,
    contains_control_or_format,
    markdown_visible_text,
    portable_identifier,
    read_strict_csv,
    spreadsheet_formula_text,
    strict_json_loads,
)


@pytest.mark.parametrize(
    "payload",
    (
        '{"state":"paid","state":"review_only"}',
        '{"value":NaN}',
        '{"value":Infinity}',
        '{"value":-Infinity}',
    ),
)
def test_strict_json_rejects_ambiguous_or_nonstandard_values(payload: str) -> None:
    with pytest.raises(StructuredDataError):
        strict_json_loads(payload)


def test_strict_csv_rejects_both_underflow_and_overflow(tmp_path: Path) -> None:
    path = tmp_path / "result.csv"
    for payload in ("id,state\nA\n", "id,state\nA,held,extra\n"):
        path.write_text(payload, encoding="utf-8")
        with pytest.raises(StructuredDataError):
            read_strict_csv(path, header=("id", "state"), max_bytes=1_000)

    path.write_text("id,state\nA,held\n", encoding="utf-8")
    assert read_strict_csv(path, header=("id", "state"), max_bytes=1_000) == [
        {"id": "A", "state": "held"}
    ]


def test_strict_csv_accepts_only_one_declared_document_bom(tmp_path: Path) -> None:
    path = tmp_path / "result.csv"
    path.write_text("\ufeffid,state\nA,held\n", encoding="utf-8")
    with pytest.raises(StructuredDataError):
        read_strict_csv(path, header=("id", "state"), max_bytes=1_000)
    assert read_strict_csv(
        path,
        header=("id", "state"),
        max_bytes=1_000,
        allow_utf8_bom=True,
    ) == [{"id": "A", "state": "held"}]

    path.write_text("\ufeffid,state\nA,he\ufeffld\n", encoding="utf-8")
    rows = read_strict_csv(
        path,
        header=("id", "state"),
        max_bytes=1_000,
        allow_utf8_bom=True,
    )
    assert contains_control_or_format(rows[0]["state"])


def test_unicode_controls_cannot_hide_formula_or_identifier_payloads() -> None:
    assert contains_control_or_format("TR\x00-1")
    assert contains_control_or_format("\ufeff=1+1")
    assert spreadsheet_formula_text("\ufeff=1+1")
    assert spreadsheet_formula_text("  =1+1")
    assert not spreadsheet_formula_text("evidence.csv#ROW-1")
    assert portable_identifier("TR200-01")
    assert not portable_identifier("TR200\n01")
    assert not portable_identifier("_TR200")
    assert not portable_identifier("A" * 65)


def test_markdown_visible_text_joins_rendered_words_and_preserves_labels() -> None:
    assert "Priya Singh" in markdown_visible_text("Pri**ya Si**ngh")
    assert "Priya Singh" in markdown_visible_text("Pri\u200bya Si\u200bngh")
    assert markdown_visible_text("[Pri](https://invalid.example)[ya](x)") == "Priya"
    assert "deleted" in markdown_visible_text("de**let**ed")
