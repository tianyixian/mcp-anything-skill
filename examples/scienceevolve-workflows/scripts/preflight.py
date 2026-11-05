"""Offline input inventory; no model calls, scientific estimates, or execution."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

VERSION = "0.1.1"
IDENTITY = {"pvdf": ("source_id", "source_locator", "sample_id", "characterization_method"),
            "pi": ("paper_id", "sample_id", "measurement_id", "property", "unit", "source_file"),
            "binder": ("source_id", "source_locator", "sample_id", "measurement_id", "measurement_type", "unit", "medium_id", "control_group")}


def check(project, workspace, stage="analysis"):
    root = Path(workspace).resolve()
    missing, invalid, hashes = [], [], {}
    warnings = ["预检只核对文件、结构和基本追溯字段；不验证数值、化学合理性、许可、模型性能或候选真实性。"]
    result = {"stage": stage, "scientific_acceptance": False, "row_count": 0}

    def record(relative):
        if not isinstance(relative, str) or not relative:
            invalid.append("输入文件路径必须为非空相对路径")
            return None
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            invalid.append("输入路径超出工作区")
            return None
        if not path.is_file():
            missing.append(relative)
            return None
        if path.stat().st_size > 50 * 1024 * 1024:
            invalid.append(relative + ": 预检文件上限50MiB；大文件请单独审查")
            return None
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path

    spec_file = record(f"inputs/{project}/run-spec.json")
    spec = None
    if spec_file:
        try:
            spec = json.loads(spec_file.read_text(encoding="utf-8-sig"))
            if not isinstance(spec, dict):
                raise ValueError("run-spec必须为对象")
            if spec.get("domain") != project:
                invalid.append("run-spec.domain 与所选方向不一致")
            if project in ("pvdf", "binder"):
                if not spec.get("target"):
                    missing.append("run-spec.target（目标、单位、测量口径）")
                paths = spec.get("source_files", [])
                if not isinstance(paths, list):
                    invalid.append("source_files必须为相对路径列表")
                else:
                    for name in paths:
                        record(name)
            else:
                targets = spec.get("targets")
                if not isinstance(targets, list) or not targets:
                    missing.append("run-spec.targets")
                else:
                    for i, target in enumerate(targets):
                        if not isinstance(target, dict):
                            invalid.append(f"targets[{i}]必须为对象")
                            continue
                        for key in ("property", "unit", "direction", "test_method", "test_conditions"):
                            if not target.get(key):
                                missing.append(f"targets[{i}].{key}")
                for key in ("material_form", "allowed_material_routes"):
                    if not spec.get(key):
                        missing.append("run-spec." + key)
            if spec.get("mechanistic_simulation") is True:
                result["mechanistic_status"] = "needs_review"
                note = "机理模拟默认关闭；开启后须另行核验结构、拓扑、力场、协议、工具和预算"
                if project == "binder":
                    warnings.append(note + "；仅暂停可选计算支线，不阻塞材料及电池的实验数据审查。")
                else:
                    missing.append(note)
        except (OSError, ValueError, UnicodeError) as error:
            invalid.append("run-spec格式错误: " + type(error).__name__)

    if stage == "analysis":
        data_file = record(f"inputs/{project}/measurements.csv")
        if data_file:
            try:
                with data_file.open(encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream)
                    fields = reader.fieldnames or []
                    if len(fields) != len(set(fields)):
                        invalid.append("CSV表头含重复列")
                    for name in IDENTITY[project]:
                        if name not in fields:
                            invalid.append("CSV缺追溯字段: " + name)
                    for row in reader:
                        if not any(value for value in row.values()):
                            continue
                        result["row_count"] += 1
                        if None in row:
                            invalid.append("CSV数据列多于表头")
                            break
                        if any(not row.get(name) for name in IDENTITY[project]):
                            missing.append(f"CSV第{reader.line_num}行缺来源/身份/口径；需补齐或隔离")
                    if not result["row_count"]:
                        missing.append("measurements.csv只有表头，没有真实记录")
            except (OSError, UnicodeError, csv.Error) as error:
                invalid.append("CSV不可读: " + type(error).__name__)

    result.update({"missing_inputs": list(dict.fromkeys(missing)), "invalid_inputs": list(dict.fromkeys(invalid))})
    status = "failed" if invalid else "needs_input" if missing else "needs_review"
    return {"status": status, "input_hash": hashes, "version": VERSION, "results": result,
            "evidence": [{"path": p, "sha256": h} for p, h in hashes.items()],
            "warnings": warnings,
            "next_step": "修正格式或补充列出的资料。" if missing or invalid else "输入格式初检通过，进入独立领域审查；不能据此声称科学结果通过。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", choices=tuple(IDENTITY), required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--stage", choices=("intake", "analysis"), default="analysis")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.project, args.workspace, args.stage)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    print(data, end="")
    return 1 if result["status"] == "failed" else 2 if result["status"] == "needs_input" else 0


if __name__ == "__main__":
    raise SystemExit(main())
