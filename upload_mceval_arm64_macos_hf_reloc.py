#!/usr/bin/env python3

from pathlib import Path

from datasets import Dataset, DatasetDict


ROOT = Path(__file__).resolve().parent
GENERATED = ROOT / "generated_mceval_arm64_mac_reloc"
DEST_REPO = "adpretko/mceval_arm_mac_reloc"

SPLITS = ["O0", "O2"]

EXPECTED_COLUMNS = [
    "task_name",
    "source_code",
    "compiler_asm",
    "object_asm",
    "shared_asm",
    "program_asm",
]


def read_text(path):
    if not path.exists():
        raise FileNotFoundError(path)

    text = path.read_text(errors="replace")

    if not text:
        raise RuntimeError(f"Empty file: {path}")

    return text


def build_split(split):
    split_root = GENERATED / split

    task_dirs = sorted(
        p for p in split_root.iterdir()
        if p.is_dir()
    )

    if len(task_dirs) != 50:
        raise RuntimeError(
            f"{split}: expected 50 tasks, "
            f"found {len(task_dirs)}"
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
                task_dir / "code.dylib.objdump"
            ),
            "program_asm": read_text(
                task_dir / "code.program.objdump"
            ),
        })

    return Dataset.from_list(rows)


def validate(ds):
    assert set(ds.keys()) == {"O0", "O2"}

    for split in SPLITS:
        d = ds[split]

        assert d.num_rows == 50
        assert d.column_names == EXPECTED_COLUMNS
        assert len(set(d["task_name"])) == 50

    assert ds["O0"]["task_name"] == ds["O2"]["task_name"]
    assert ds["O0"]["source_code"] == ds["O2"]["source_code"]

    print("O0: PASS — 50 rows")
    print("O2: PASS — 50 rows")
    print("O0/O2 task ordering: PASS")
    print("O0/O2 source_code identity: PASS")


def main():
    ds = DatasetDict({
        "O0": build_split("O0"),
        "O2": build_split("O2"),
    })

    validate(ds)

    print()
    print(ds)

    print()
    print("=" * 80)
    print(f"UPLOADING -> {DEST_REPO}")
    print("=" * 80)

    ds.push_to_hub(DEST_REPO)

    print()
    print("=" * 80)
    print("UPLOAD COMPLETE")
    print("=" * 80)
    print(DEST_REPO)


if __name__ == "__main__":
    main()
