#!/usr/bin/env python3
import argparse, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPLITS = ["O0","O2"]
NUM_TASKS = 50
TARGETS = {
    "x86_linux": {"cc":"gcc","objdump":"objdump","flags":["-march=x86-64"],"generated":ROOT/"generated_mceval_x86_linux_reloc","format":"elf64-x86-64"},
    "arm_linux": {"cc":"aarch64-linux-gnu-gcc","objdump":"aarch64-linux-gnu-objdump","flags":["-march=armv8-a"],"generated":ROOT/"generated_mceval_arm64_linux_reloc","format":"elf64-littleaarch64"},
    "riscv_linux": {"cc":"riscv64-linux-gnu-gcc","objdump":"riscv64-linux-gnu-objdump","flags":["-march=rv64gc","-mabi=lp64d"],"generated":ROOT/"generated_mceval_riscv64_linux_reloc","format":"elf64-littleriscv"},
}

def run(cmd, stdout_path=None):
    cmd=list(map(str,cmd))
    print("+"," ".join(cmd))
    if stdout_path:
        with stdout_path.open("w",encoding="utf-8") as f:
            r=subprocess.run(cmd,text=True,stdout=f,stderr=subprocess.PIPE)
    else:
        r=subprocess.run(cmd,text=True,capture_output=True)
    if r.returncode:
        raise RuntimeError("Command failed:\n"+" ".join(cmd)+"\n"+(r.stderr or ""))

def req(p):
    if not p.is_file() or p.stat().st_size==0:
        raise RuntimeError(f"Missing/empty: {p}")

def build_one(target, cfg, split, td):
    opt="-O0" if split=="O0" else "-O2"
    src=td/"source.c"
    picobj=td/"code.pic.o"
    for p in [src,picobj,td/"code.o.objdump",td/"code.so.objdump",td/"code.program.objdump"]:
        req(p)

    pics=td/"compiler.pic.s"
    picdump=td/"code.pic.o.objdump"

    run([cfg["cc"],*cfg["flags"],opt,"-fPIC","-S",src,"-o",pics])
    req(pics)

    run([cfg["objdump"],"-dr",picobj],stdout_path=picdump)
    req(picdump)

    if cfg["format"] not in picdump.read_text(errors="replace"):
        raise RuntimeError(f"{target} {split} {td.name}: wrong object format")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--target",action="append",choices=sorted(TARGETS))
    ap.add_argument("--split",action="append",choices=SPLITS)
    a=ap.parse_args()
    targets=a.target or list(TARGETS)
    splits=a.split or SPLITS

    for t in targets:
        c=TARGETS[t]
        for tool in (c["cc"],c["objdump"]):
            if shutil.which(tool) is None:
                raise SystemExit(f"{t}: missing tool {tool}")

    failures=[]
    done=0
    for t in targets:
        c=TARGETS[t]
        for split in splits:
            root=c["generated"]/split
            tds=sorted(p for p in root.iterdir() if p.is_dir())
            if len(tds)!=NUM_TASKS:
                raise SystemExit(f"{t} {split}: expected 50 task dirs, found {len(tds)}")
            for i,td in enumerate(tds,1):
                print(f"===== {t} {split}: {td.name} ({i}/50) =====")
                try:
                    build_one(t,c,split,td)
                    done+=1
                except Exception as e:
                    print("FAILED:",e)
                    failures.append((t,split,td.name,str(e)))

    expected=len(targets)*len(splits)*NUM_TASKS
    print("\n"+"="*78)
    print("MC-EVAL PIC REFERENCE GENERATION SUMMARY")
    print("="*78)
    print(f"Expected instances:  {expected}")
    print(f"Completed instances: {done}")
    print(f"Failures:             {len(failures)}")
    if failures or done!=expected:
        for x in failures: print(" ",*x)
        raise SystemExit(1)
    print("OVERALL: PASS")

if __name__=="__main__":
    main()
