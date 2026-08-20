#!/usr/bin/env python3

"""
Enrich the EXISTING live MC-Eval ARM64 macOS reloc dataset on Hugging Face
with the two PIC-reference columns generated locally:

    compiler_pic_asm
    pic_object_asm

Target repo:
    adpretko/mceval_arm_mac_reloc

Local tree:
    generated_mceval_arm64_mac_reloc/{O0,O2}/...

Safety:
- Loads the CURRENT live HF dataset first, preserving its row order.
- Verifies every existing six-column HF row matches the corresponding local files.
- Adds only the two new PIC columns.
- Refuses to upload unless all checks pass.
- --validate-only performs every check but does not push.
- --verify-live reloads the live HF dataset and checks final shape/schema.
"""

import argparse
from pathlib import Path

from datasets import Dataset, DatasetDict, load_dataset

ROOT = Path(__file__).resolve().parent
GENERATED = ROOT / "generated_mceval_arm64_mac_reloc"

TARGET_REPO = "adpretko/mceval_arm_mac_reloc"

SPLITS = ("O0", "O2")
EXPECTED_ROWS = 50

OLD_COLUMNS = [
    "task_name",
    "source_code",
    "compiler_asm",
    "object_asm",
    "shared_asm",
    "program_asm",
]

FINAL_COLUMNS = OLD_COLUMNS + [
    "compiler_pic_asm",
    "pic_object_asm",
]

LOCAL_FILES = {
    "source_code": "source.c",
    "compiler_asm": "compiler.s",
    "object_asm": "code.o.objdump",
    "shared_asm": "code.dylib.objdump",
    "program_asm": "code.program.objdump",
    "compiler_pic_asm": "compiler.pic.s",
    "pic_object_asm": "code.pic.o.objdump",
}


def read_text(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"Missing file: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")

    if not text:
        raise RuntimeError(f"Empty file: {path}")

    return text


def task_name_from_dir(task_dir: Path) -> str:
    # Example: 000_C_1 -> C_1
    if "_" not in task_dir.name:
        raise RuntimeError(
            f"Unexpected task directory name: {task_dir.name}"
        )

    return task_dir.name.split("_", 1)[1]


def build_local_index(split: str):
    split_dir = GENERATED / split

    if not split_dir.is_dir():
        raise RuntimeError(f"Missing split directory: {split_dir}")

    task_dirs = sorted(
        p for p in split_dir.iterdir()
        if p.is_dir()
    )

    if len(task_dirs) != EXPECTED_ROWS:
        raise RuntimeError(
            f"{split}: expected {EXPECTED_ROWS} task directories, "
            f"found {len(task_dirs)}"
        )

    index = {}

    for task_dir in task_dirs:
        task_name = task_name_from_dir(task_dir)

        if task_name in index:
            raise RuntimeError(
                f"{split}: duplicate local task_name {task_name}"
            )

        # Require every expected artifact to exist before accepting the row.
        for filename in LOCAL_FILES.values():
            read_text(task_dir / filename)

        index[task_name] = task_dir

    return index


def validate_existing_row(
    split: str,
    row_index: int,
    row,
    task_dir: Path,
):
    task_name = row["task_name"]

    # task_name itself comes from the HF row / directory mapping.
    # Compare all other original six columns byte-for-text against local files.
    for column in OLD_COLUMNS[1:]:
        local_text = read_text(task_dir / LOCAL_FILES[column])
        hf_text = row[column]

        if hf_text != local_text:
            raise RuntimeError(
                f"{split} row {row_index} ({task_name}): "
                f"live HF column {column!r} does not match "
                f"local file {LOCAL_FILES[column]!r}"
            )


def build_enriched_split(split: str, live_split):
    if live_split.num_rows != EXPECTED_ROWS:
        raise RuntimeError(
            f"{split}: live HF has {live_split.num_rows} rows; "
            f"expected {EXPECTED_ROWS}"
        )

    if live_split.column_names != OLD_COLUMNS:
        raise RuntimeError(
            f"{split}: unexpected live HF columns\n"
            f"Expected: {OLD_COLUMNS}\n"
            f"Actual:   {live_split.column_names}"
        )

    local_index = build_local_index(split)

    hf_task_names = list(live_split["task_name"])

    if len(set(hf_task_names)) != EXPECTED_ROWS:
        raise RuntimeError(
            f"{split}: duplicate task_name values in live HF dataset"
        )

    hf_names = set(hf_task_names)
    local_names = set(local_index)

    if hf_names != local_names:
        missing_local = sorted(hf_names - local_names)
        extra_local = sorted(local_names - hf_names)

        raise RuntimeError(
            f"{split}: HF/local task-name mismatch\n"
            f"Missing locally: {missing_local}\n"
            f"Extra locally:   {extra_local}"
        )

    output = {
        column: []
        for column in FINAL_COLUMNS
    }

    for i, row in enumerate(live_split):
        task_name = row["task_name"]
        task_dir = local_index[task_name]

        # Prove that we are enriching the exact current live dataset.
        validate_existing_row(
            split,
            i,
            row,
            task_dir,
        )

        for column in OLD_COLUMNS:
            output[column].append(row[column])

        output["compiler_pic_asm"].append(
            read_text(
                task_dir / LOCAL_FILES["compiler_pic_asm"]
            )
        )

        output["pic_object_asm"].append(
            read_text(
                task_dir / LOCAL_FILES["pic_object_asm"]
            )
        )

    ds = Dataset.from_dict(output)

    if ds.num_rows != EXPECTED_ROWS:
        raise RuntimeError(
            f"{split}: final dataset has {ds.num_rows} rows; "
            f"expected {EXPECTED_ROWS}"
        )

    if ds.column_names != FINAL_COLUMNS:
        raise RuntimeError(
            f"{split}: final column order mismatch\n"
            f"Expected: {FINAL_COLUMNS}\n"
            f"Actual:   {ds.column_names}"
        )

    if any(
        not value.strip()
        for value in ds["compiler_pic_asm"]
    ):
        raise RuntimeError(
            f"{split}: empty compiler_pic_asm value found"
        )

    if any(
        not value.strip()
        for value in ds["pic_object_asm"]
    ):
        raise RuntimeError(
            f"{split}: empty pic_object_asm value found"
        )

    return ds


def verify_live():
    print()
    print("=" * 78)
    print("RELOADING LIVE HUGGING FACE DATASET")
    print("=" * 78)

    live = load_dataset(
        TARGET_REPO,
        download_mode="force_redownload",
    )

    if set(live.keys()) != set(SPLITS):
        raise RuntimeError(
            f"Unexpected live splits: {list(live.keys())}"
        )

    for split in SPLITS:
        ds = live[split]

        print(f"{split}: {ds.num_rows} rows")
        print(f"{split}: {ds.column_names}")

        if ds.num_rows != EXPECTED_ROWS:
            raise RuntimeError(
                f"{split}: expected {EXPECTED_ROWS} live rows, "
                f"got {ds.num_rows}"
            )

        if ds.column_names != FINAL_COLUMNS:
            raise RuntimeError(
                f"{split}: live column mismatch"
            )

        if any(
            not value.strip()
            for value in ds["compiler_pic_asm"]
        ):
            raise RuntimeError(
                f"{split}: empty live compiler_pic_asm value"
            )

        if any(
            not value.strip()
            for value in ds["pic_object_asm"]
        ):
            raise RuntimeError(
                f"{split}: empty live pic_object_asm value"
            )

    # Preserve original MC-Eval invariants too.
    if live["O0"]["task_name"] != live["O2"]["task_name"]:
        raise RuntimeError(
            "Live O0/O2 task ordering differs"
        )

    if live["O0"]["source_code"] != live["O2"]["source_code"]:
        raise RuntimeError(
            "Live O0/O2 source_code differs"
        )

    print("O0/O2 task ordering: PASS")
    print("O0/O2 source_code identity: PASS")
    print("LIVE HF VERIFICATION: PASS")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate/package locally but do not upload.",
    )

    parser.add_argument(
        "--verify-live",
        action="store_true",
        help="Only reload and verify the current live HF dataset.",
    )

    args = parser.parse_args()

    if args.verify_live:
        verify_live()
        return

    if not GENERATED.is_dir():
        raise SystemExit(
            f"Missing generated dataset root:\n{GENERATED}"
        )

    print("=" * 78)
    print("LOADING CURRENT LIVE MC-EVAL ARM64 MACOS DATASET")
    print("=" * 78)
    print(TARGET_REPO)

    live = load_dataset(TARGET_REPO)

    if set(live.keys()) != set(SPLITS):
        raise RuntimeError(
            f"Unexpected live splits: {list(live.keys())}"
        )

    enriched = {}

    for split in SPLITS:
        print()
        print("=" * 78)
        print(f"VALIDATING + ENRICHING {split}")
        print("=" * 78)

        enriched[split] = build_enriched_split(
            split,
            live[split],
        )

        print(
            f"{split}: rows = "
            f"{enriched[split].num_rows}"
        )
        print(
            f"{split}: columns = "
            f"{enriched[split].column_names}"
        )
        print(f"{split}: PASS")

    dataset_dict = DatasetDict(enriched)

    # Preserve the original uploader's cross-split invariants.
    if (
        dataset_dict["O0"]["task_name"]
        != dataset_dict["O2"]["task_name"]
    ):
        raise RuntimeError(
            "O0/O2 task ordering differs"
        )

    if (
        dataset_dict["O0"]["source_code"]
        != dataset_dict["O2"]["source_code"]
    ):
        raise RuntimeError(
            "O0/O2 source_code differs"
        )

    print()
    print("=" * 78)
    print("LOCAL PACKAGING SUMMARY")
    print("=" * 78)

    for split in SPLITS:
        print(
            f"{split}: {dataset_dict[split].num_rows} rows, "
            f"{len(dataset_dict[split].column_names)} columns"
        )

    print("O0/O2 task ordering: PASS")
    print("O0/O2 source_code identity: PASS")
    print("LOCAL VALIDATION: PASS")
    print("Final columns:", FINAL_COLUMNS)

    if args.validate_only:
        print(
            "No upload performed (--validate-only)."
        )
        return

    print()
    print("=" * 78)
    print("UPLOADING TO HUGGING FACE")
    print("=" * 78)
    print(TARGET_REPO)

    dataset_dict.push_to_hub(TARGET_REPO)

    print("UPLOAD COMPLETE")

    verify_live()


if __name__ == "__main__":
    main()
