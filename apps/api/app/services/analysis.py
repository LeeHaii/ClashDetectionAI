from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from app.db.models import ClashItem, InferenceRun
from app.schemas.analysis import ElementMetadata, NormalizedAnalysis, VisualAnalysis


class InvalidModelOutput(ValueError):
    pass


class PromptBuilder:
    def __init__(self, prompt_version: str) -> None:
        self.prompt_version = prompt_version
        prompt_path = (
            Path(__file__).parents[1] / "prompts" / f"{prompt_version.replace('-', '_')}.txt"
        )
        if not prompt_path.is_file():
            prompt_path = Path(__file__).parents[1] / "prompts" / "clash_analysis_v1.txt"
        self.template = prompt_path.read_text(encoding="utf-8")

    def build(self, *, question: str, clash: ClashItem | None) -> str:
        context: dict[str, Any]
        if clash is None:
            context = {"mode": "image-chat", "trusted_metadata": "No report record selected"}
        else:
            context = {
                "distance_m": clash.distance_m,
                "distance_original": clash.distance_raw,
                "grid": clash.grid,
                "clash_point": clash.clash_point,
                "elements": clash.elements,
            }
        return self.template.format(
            context=json.dumps(context, ensure_ascii=False, indent=2), question=question.strip()
        )


class AnalysisNormalizer:
    _canonical_values = {
        "clash_type": {
            "inserted": "Inserted",
            "intersected": "Intersected",
            "penetrated through": "Penetrated through",
            "penetrated": "Penetrated through",
        },
        "orientation": {
            "horizontal": "Horizontal",
            "vertical": "Vertical",
            "diagonal": "Diagonal",
        },
        "cross_sectional_shape": {
            "circular": "Circular",
            "rectangular": "Rectangular",
            "irregular": "Irregular shape",
            "irregular shape": "Irregular shape",
        },
        "cross_sectional_size": {
            "small": "Small",
            "medium": "Medium",
            "large": "Large",
        },
    }

    def __init__(self, *, parser_version: str, severity_rule_version: str) -> None:
        self.parser_version = parser_version
        self.severity_rule_version = severity_rule_version

    def normalize(
        self, raw_output: str, run: InferenceRun, clash: ClashItem | None
    ) -> NormalizedAnalysis:
        visual = self.parse_visual(raw_output)
        if not visual.clash:
            visual = VisualAnalysis(clash=False, explanation=visual.explanation)
        elements = [
            ElementMetadata.model_validate(value) for value in (clash.elements if clash else [])
        ]
        severity = self._severity(visual.clash, clash.distance_m if clash else None)
        return NormalizedAnalysis(
            **visual.model_dump(),
            clash_name=clash.clash_id if clash else "Image analysis",
            elements=elements,
            severity=severity,
            recommended_action=self._recommended_action(visual, severity, clash),
            report_id=clash.report_id if clash else None,
            clash_item_id=clash.id if clash else None,
            model_name=run.model_name,
            adapter_version=run.adapter_version,
            prompt_version=run.prompt_version,
            parser_version=self.parser_version,
            severity_rule_version=self.severity_rule_version,
        )

    def parse_visual(self, raw_output: str) -> VisualAnalysis:
        fields = self._parse_fields(raw_output)
        clash_text = self._lookup(fields, "clash")
        if clash_text is None:
            raise InvalidModelOutput("Model output is missing the Clash field")
        normalized_clash = self._clean(clash_text).casefold()
        if normalized_clash not in {"true", "false"}:
            raise InvalidModelOutput("Clash must be True or False")
        is_clash = normalized_clash == "true"
        values: dict[str, Any] = {"clash": is_clash}
        for field in self._canonical_values:
            raw_value = self._lookup(fields, field)
            values[field] = self._canonical(field, raw_value) if is_clash else None
        explanation = self._lookup(fields, "explanation")
        if explanation:
            values["explanation"] = self._clean(explanation)[:2_000]
        try:
            return VisualAnalysis.model_validate(values)
        except ValidationError as error:
            raise InvalidModelOutput(str(error)) from error

    def to_markdown(self, result: NormalizedAnalysis) -> str:
        objects = (
            " vs ".join(
                f"ID {self._escape(element.element_id or 'Unknown')} "
                f"({self._escape(element.layer or 'Unknown layer')})"
                for element in result.elements
            )
            or "Not provided"
        )
        rows = [
            ("Clash name", result.clash_name),
            ("Clash", "True" if result.clash else "False"),
            ("Clash type", result.clash_type or "None"),
            ("Orientation", result.orientation or "None"),
            ("Cross-sectional shape", result.cross_sectional_shape or "None"),
            ("Cross-sectional size", result.cross_sectional_size or "None"),
            ("Objects", objects),
            ("Severity", result.severity),
            ("Recommended action", result.recommended_action or "None"),
        ]
        return "| Field | Value |\n|---|---|\n" + "\n".join(
            f"| **{field}** | {self._escape(str(value))} |" for field, value in rows
        )

    def _parse_fields(self, raw_output: str) -> dict[str, str]:
        stripped = raw_output.strip()
        if stripped.startswith("{"):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise InvalidModelOutput("Model returned invalid JSON") from error
            if not isinstance(value, dict):
                raise InvalidModelOutput("Model JSON output must be an object")
            return {self._key(str(key)): str(item) for key, item in value.items()}

        table_rows: list[list[str]] = []
        for line in stripped.splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            table_rows.append(cells)
        if len(table_rows) < 2:
            raise InvalidModelOutput("Model output is not a recognized Markdown table")

        if len(table_rows[0]) == 2 and self._key(table_rows[0][0]) in {"field", "attribute"}:
            return {
                self._key(row[0]): row[1]
                for row in table_rows[1:]
                if len(row) >= 2 and row[0].strip()
            }
        headers = [self._key(value) for value in table_rows[0]]
        values = table_rows[1]
        return {
            header: values[index] for index, header in enumerate(headers) if index < len(values)
        }

    def _canonical(self, field: str, raw_value: str | None) -> str | None:
        if raw_value is None:
            return None
        cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", self._clean(raw_value)).casefold()
        if cleaned in {"none", "unknown", "n/a", ""}:
            return None
        value = self._canonical_values[field].get(cleaned)
        if value is None:
            raise InvalidModelOutput(f"Unsupported {field.replace('_', ' ')} value: {raw_value}")
        return value

    @staticmethod
    def _severity(
        clash: bool, distance_m: float | None
    ) -> Literal["None", "Low", "Medium", "High"]:
        if not clash:
            return "None"
        penetration = abs(min(distance_m or 0.0, 0.0))
        if penetration >= 0.1:
            return "High"
        if penetration >= 0.05:
            return "Medium"
        return "Low"

    @staticmethod
    def _recommended_action(
        visual: VisualAnalysis, severity: str, clash: ClashItem | None
    ) -> str | None:
        if not visual.clash:
            return None
        location = f" near {clash.grid}" if clash and clash.grid else ""
        if severity == "High":
            return f"Escalate coordination and reroute the flexible element{location}."
        if severity == "Medium":
            return f"Review design priority and adjust the flexible element{location}."
        return f"Verify tolerances and coordinate a local adjustment{location}."

    @classmethod
    def _lookup(cls, fields: dict[str, str], key: str) -> str | None:
        aliases = {
            "clash_type": ["clash type", "type"],
            "cross_sectional_shape": ["cross sectional shape", "shape"],
            "cross_sectional_size": ["cross sectional size", "size"],
            "explanation": ["explanation", "reason"],
        }
        for candidate in aliases.get(key, [key.replace("_", " ")]):
            value = fields.get(cls._key(candidate))
            if value is not None:
                return value
        return None

    @staticmethod
    def _key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.replace("**", "").casefold()).strip()

    @staticmethod
    def _clean(value: str) -> str:
        return value.replace("**", "").strip()

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


@dataclass(frozen=True)
class ModelInput:
    prompt: str
    image_path: Path | None
    history: list[dict[str, str]]
