# MC-Eval Binary Generation

This repository contains the scripts used to generate MC-Eval binary-derived assembly datasets for:

- x86-64 Linux
- ARM64 Linux
- RISC-V64 Linux
- ARM64 macOS

For each MC-Eval task and optimization level (`O0` and `O2`), the datasets contain:

- `task_name` — MC-Eval task identifier
- `source_code` — original C source
- `compiler_asm` — compiler-generated assembly from `clang -S`
- `object_asm` — disassembly of the relocatable object file
- `shared_asm` — disassembly of the linked shared library
- `program_asm` — disassembly of the linked executable

The final relocation-preserving datasets use:

- Relocatable objects: `llvm-objdump -dr`
- Linked shared libraries: `llvm-objdump -drR`
- Linked executables: `llvm-objdump -drR`

The relocation flags are important because plain `objdump -d` omits relocation information that is present in relocatable object files.

## Linux

### `build_mceval_linux.py`

Original Linux generation script.

It compiles MC-Eval for the supported Linux targets and generates compiler assembly, relocatable objects, shared libraries, executables, and their disassembly.

The original binary disassembly used plain `-d`.

### `build_mceval_linux_reloc.py`

Relocation-preserving Linux generation script.

It generates the corrected Linux datasets using:

- `.o` -> `objdump -dr`
- shared library -> `objdump -drR`
- executable -> `objdump -drR`

The corrected outputs are stored separately from the original datasets.

### `validate_mceval_linux_reloc.py`

Validates the locally generated relocation-preserving Linux datasets.

The validation checks that:

- the expected tasks and optimization splits are present;
- source code is preserved;
- compiler-generated assembly is consistent with the original generation;
- the underlying instruction disassembly has not unexpectedly changed;
- saved objdump output exactly matches fresh `-dr` / `-drR` invocations;
- generated binaries have the expected target formats.

### `upload_mceval_linux_hf.py`

Uploads the original Linux datasets to Hugging Face.

### `upload_mceval_linux_hf_reloc.py`

Builds Hugging Face `DatasetDict` objects from the relocation-preserving Linux outputs and uploads the corrected datasets.

### `validate_mceval_linux_hf.py`

Loads the uploaded relocation-preserving datasets back from Hugging Face and verifies that every uploaded row and field exactly matches the corresponding local dataset.

## ARM64 macOS

### `build_mceval_arm64_macos.py`

Original ARM64 macOS generation script.

For each task it produces:

- `source.c`
- `program_source.c`
- `compiler.s`
- `code.o`
- `code.o.objdump`
- `code.pic.o`
- `code.dylib`
- `code.dylib.objdump`
- `code.program`
- `code.program.objdump`

The synthetic `main()` in `program_source.c` is used only to make it possible to link an executable. The original MC-Eval source is preserved unchanged in `source.c`.

### Why macOS uses a refresh workflow

The corrected macOS dataset is intentionally not rebuilt into a differently named output directory.

Mach-O dynamic libraries contain an `LC_ID_DYLIB` load command. Rebuilding a dylib under a longer `_reloc` path can change the embedded dylib path, increase the size of the load command, and shift the linked Mach-O layout.

To ensure that the corrected dataset uses exactly the same original binary artifacts, the macOS correction therefore uses this workflow:

1. Copy the original generated directory byte-for-byte to a `_reloc` directory.
2. Leave all source files, compiler assembly, objects, dylibs, and executables unchanged.
3. Regenerate only the `.objdump` files using the relocation-preserving flags.
4. Validate that every non-`.objdump` artifact remains byte-for-byte identical.

This avoids introducing binary changes caused only by rebuilding under a different filesystem path.

### `refresh_mceval_arm64_macos_objdump_reloc.py`

Regenerates only the objdump text from the copied original binaries:

- `code.o` -> `llvm-objdump -dr`
- `code.dylib` -> `llvm-objdump -drR`
- `code.program` -> `llvm-objdump -drR`

All other files remain untouched.

### `validate_mceval_arm64_macos_reloc.py`

Performs local validation of the corrected macOS dataset.

It verifies that:

- both `O0` and `O2` contain all 50 MC-Eval tasks;
- the old and new directory/file layouts match;
- every non-`.objdump` file is byte-for-byte identical to the original;
- every new `.objdump` file exactly matches a fresh invocation of the intended `-dr` or `-drR` command;
- the binary format is ARM64 Mach-O.

### `upload_mceval_arm64_macos_hf.py`

Uploads the original ARM64 macOS dataset.

### `upload_mceval_arm64_macos_hf_reloc.py`

Builds the corrected ARM64 macOS `DatasetDict` from the `_reloc` output directory and uploads it to `adpretko/mceval_arm_mac_reloc`.

### `validate_mceval_arm64_macos_hf.py`

Downloads the uploaded relocation-preserving macOS dataset and compares all 100 rows (`50 O0 + 50 O2`) and every field exactly against the locally reconstructed dataset.

## Recommended workflow

### Linux

1. Run `build_mceval_linux_reloc.py`.
2. Run `validate_mceval_linux_reloc.py`.
3. Run `upload_mceval_linux_hf_reloc.py`.
4. Run `validate_mceval_linux_hf.py`.

### macOS

1. Copy `generated_mceval_arm64_mac` to `generated_mceval_arm64_mac_reloc`.
2. Run `refresh_mceval_arm64_macos_objdump_reloc.py`.
3. Run `validate_mceval_arm64_macos_reloc.py`.
4. Run `upload_mceval_arm64_macos_hf_reloc.py`.
5. Run `validate_mceval_arm64_macos_hf.py`.

The original scripts and datasets are retained for reproducibility. The `_reloc` versions are the corrected datasets that preserve relocation information in the binary-derived assembly.
