#!/usr/bin/env python3

from pathlib import Path

from datasets import Dataset, DatasetDict


ROOT = Path(__file__).resolve().parent

TARGETS = {
    "x86_linux": {
        "generated": ROOT / "generated_mceval_x86_linux",
        "repo_id": "adpretko/mceval_x86_linux",
    },
    "arm_linux": {
        "generated": ROOT / "generated_mceval_arm64_linux",
        "repo_id": "adpretko/mceval_arm_linux",
    },
    "riscv_linux": {
        "generated": ROOT / "generated_mceval_riscv64_linux",
        "repo_id": "adpretko/mceval_riscv_linux",
    },
}

SPLITS = ["O0", "O2"]


def read_text(path):
    if not path.exists():
        raise FileNotFoundError(path)

    text = path.read_text(errors="replace")

    if not text:
        raise RuntimeError(f"Empty file: {path}")

    return text


def build_split(root, split):
    task_dirs = sorted(
        p for p in (root / split).iterdir()
        if p.is_dir()
    )

    if len(task_dirs) != 50:
        raise RuntimeError(
            f"{root.name} {split}: "
            f"expected 50 tasks, found {len(task_dirs)}"
        )

    rows = []

    for task_dir in task_dirs:
        # Example:
        # 000_C_1 -> C_1
        task_name = task_dir.name.split("_", 1)[1]

        rows.append({
            "task_name": task_name,
            "source_code": read_text(
                task_dir / "source.c"
            ),
            "compiler_asm": read_text(
                task_dir / "compiler.s"
            ),
            "object_asm": read_text(
                task_dir / "code.o.objdump"
            ),
            "shared_asm": read_text(
                task_dir / "code.so.objdump"
            ),
            "program_asm": read_text(
                task_dir / "code.program.objdump"
            ),
        })

    return Dataset.from_list(rows)


def main():
    for target, config in TARGETS.items():
        print()
        print("=" * 80)
        print(f"UPLOADING {target}")
        print(f"-> {config['repo_id']}")
        print("=" * 80)

        ds = DatasetDict({
            "O0": build_split(
                config["generated"],
                "O0",
            ),
            "O2": build_split(
                config["generated"],
                "O2",
            ),
        })

        # Minimal safety checks before each push.
        assert len(ds["O0"]) == 50
        assert len(ds["O2"]) == 50
        assert ds["O0"]["task_name"] == ds["O2"]["task_name"]
        assert ds["O0"]["source_code"] == ds["O2"]["source_code"]

        ds.push_to_hub(config["repo_id"])

        print(f"UPLOAD COMPLETE: {config['repo_id']}")

    print()
    print("=" * 80)
    print("ALL THREE MC-EVAL UPLOADS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
