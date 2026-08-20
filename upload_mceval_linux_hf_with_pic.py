#!/usr/bin/env python3
import argparse
from pathlib import Path
from datasets import Dataset, DatasetDict

ROOT=Path(__file__).resolve().parent
NUM_TASKS=50
SPLITS=["O0","O2"]
TARGETS={
    "x86_linux":{"generated":ROOT/"generated_mceval_x86_linux_reloc","repo_id":"adpretko/mceval_x86_linux_reloc"},
    "arm_linux":{"generated":ROOT/"generated_mceval_arm64_linux_reloc","repo_id":"adpretko/mceval_arm_linux_reloc"},
    "riscv_linux":{"generated":ROOT/"generated_mceval_riscv64_linux_reloc","repo_id":"adpretko/mceval_riscv_linux_reloc"},
}
EXPECTED_COLUMNS=[
    "task_name","source_code","compiler_asm","object_asm",
    "shared_asm","program_asm","compiler_pic_asm","pic_object_asm",
]

def read_text(p):
    if not p.exists(): raise FileNotFoundError(p)
    s=p.read_text(errors="replace")
    if not s: raise RuntimeError(f"Empty file: {p}")
    return s

def task_name(td):
    parts=td.name.split("_",1)
    if len(parts)!=2: raise RuntimeError(f"Unexpected task dir: {td.name}")
    return parts[1]

def build_split(root, split):
    tds=sorted(p for p in (root/split).iterdir() if p.is_dir())
    if len(tds)!=NUM_TASKS:
        raise RuntimeError(f"{root.name} {split}: expected 50 tasks, found {len(tds)}")
    rows=[]
    for td in tds:
        rows.append({
            "task_name":task_name(td),
            "source_code":read_text(td/"source.c"),
            "compiler_asm":read_text(td/"compiler.s"),
            "object_asm":read_text(td/"code.o.objdump"),
            "shared_asm":read_text(td/"code.so.objdump"),
            "program_asm":read_text(td/"code.program.objdump"),
            "compiler_pic_asm":read_text(td/"compiler.pic.s"),
            "pic_object_asm":read_text(td/"code.pic.o.objdump"),
        })
    return Dataset.from_list(rows)

def validate(t,ds):
    assert set(ds.keys())=={"O0","O2"}
    for split in SPLITS:
        d=ds[split]
        assert d.num_rows==NUM_TASKS
        assert d.column_names==EXPECTED_COLUMNS
        assert len(set(d["task_name"]))==NUM_TASKS
        for row in d:
            for col in EXPECTED_COLUMNS:
                if not row[col]:
                    raise RuntimeError(f"{t} {split} {row['task_name']}: empty {col}")
        print(f"{t} {split}: PASS")
        print(f"  rows: {d.num_rows}")
        print(f"  columns: {d.column_names}")
    assert ds["O0"]["task_name"]==ds["O2"]["task_name"]
    assert ds["O0"]["source_code"]==ds["O2"]["source_code"]
    print(f"{t} O0/O2 task ordering: PASS")
    print(f"{t} O0/O2 source_code identity: PASS")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--target",action="append",choices=sorted(TARGETS))
    ap.add_argument("--validate-only",action="store_true")
    a=ap.parse_args()
    selected=a.target or list(TARGETS)
    built={}

    for t in selected:
        c=TARGETS[t]
        print("\n"+"="*78)
        print(f"BUILDING DATASET: {t}")
        print("="*78)
        ds=DatasetDict({
            "O0":build_split(c["generated"],"O0"),
            "O2":build_split(c["generated"],"O2"),
        })
        validate(t,ds)
        built[t]=ds

    print("\n"+"="*78)
    print("ALL SELECTED LOCAL DATASETS VALIDATED")
    print("="*78)
    if a.validate_only:
        print("VALIDATE-ONLY requested: nothing uploaded.")
        return

    for t in selected:
        repo=TARGETS[t]["repo_id"]
        print("\n"+"="*78)
        print(f"UPLOADING {t}")
        print(f"-> {repo}")
        print("="*78)
        built[t].push_to_hub(repo)
        print(f"UPLOAD COMPLETE: {repo}")

if __name__=="__main__":
    main()
