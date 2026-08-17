from app.db.models import ClashItem, InferenceRun
from app.services.analysis import AnalysisNormalizer, InvalidModelOutput


def normalizer() -> AnalysisNormalizer:
    return AnalysisNormalizer(parser_version="navisworks-v1", severity_rule_version="severity-v1")


def run() -> InferenceRun:
    return InferenceRun(
        model_name="Qwen/Qwen2.5-VL-7B-Instruct",
        adapter_version="train_2026-07-29-14-13-40",
        prompt_version="clash-analysis-v1",
    )


def clash() -> ClashItem:
    return ClashItem(
        id="clash-item-1",
        report_id="report-1",
        clash_id="trusted-name",
        row_index=1,
        distance_m=-0.12,
        elements=[
            {"element_id": "trusted-123", "layer": "Level 1", "size": "50mm", "metadata": {}},
            {"element_id": "trusted-456", "layer": "Level 2", "size": None, "metadata": {}},
        ],
        source_metadata={},
    )


def test_replaces_model_metadata_and_derives_severity() -> None:
    raw = """| Field | Value |
|---|---|
| Clash name | hallucinated-name |
| Clash | True |
| Clash type | penetrated |
| Orientation | vertical |
| Cross-sectional shape | circular |
| Cross-sectional size | Small (50mm) |
| Objects | hallucinated objects |
| Severity | Low |
| Explanation | Visible penetration. |"""

    result = normalizer().normalize(raw, run(), clash())

    assert result.clash_name == "trusted-name"
    assert result.elements[0].element_id == "trusted-123"
    assert result.clash_type == "Penetrated through"
    assert result.cross_sectional_size == "Small"
    assert result.severity == "High"


def test_no_clash_clears_inapplicable_fields() -> None:
    raw = """| Field | Value |
|---|---|
| Clash | False |
| Clash type | Intersected |
| Orientation | Vertical |
| Cross-sectional shape | Circular |
| Cross-sectional size | Large |"""

    result = normalizer().normalize(raw, run(), clash())

    assert result.severity == "None"
    assert result.clash_type is None
    assert result.recommended_action is None


def test_rejects_unknown_enum_value() -> None:
    raw = """| Field | Value |
|---|---|
| Clash | True |
| Clash type | Teleported |"""
    try:
        normalizer().normalize(raw, run(), clash())
    except InvalidModelOutput as error:
        assert "Unsupported clash type" in str(error)
    else:
        raise AssertionError("Invalid model output was accepted")
