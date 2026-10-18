# FABulous for OWAS

This repository provides the OWAS project's FABulous fabric generation,
mapping and bitstream workflow. The CrocoScale FPGA fabric is included as the
`OWAS_fabric` submodule, including its FLUT5 tile library.

## Clone and update

Clone with all nested submodules:

```bash
git clone --recurse-submodules git@github.com:FPGA-Research/FABulous-OWAS.git
cd FABulous-OWAS
```

Update the repository and check out its recorded submodule versions:

```bash
git pull
git submodule update --init --recursive
```

To advance submodules to their configured remote branches instead:

```bash
git submodule update --init --remote --recursive
```

## Set up the environment

Install `uv`, then run from this repository's root:

```bash
uv sync
source .venv/bin/activate
```

This also makes `task` available. SSH access to `FPGA-Research/FAB-mapper` is
required: `task fab_mapper` runs it through `uvx` in a separate cached environment
and checks for upstream updates. Push mapper changes to GitHub before running
this task to use them.

Use the [hausdinge/nextpnr fork](https://github.com/hausdinge/nextpnr) for routing.
It fixes the FABulous constant-driver pin directions that can cause Router2 to
fail. Build `nextpnr-generic` alongside this repository using system build tools,
outside the OSS CAD Suite environment. The build needs CMake, Ninja, a C++17
compiler, Boost, Eigen3 and Python development headers.

```bash
git clone https://github.com/hausdinge/nextpnr.git ../nextpnr
cmake -S ../nextpnr -B ../nextpnr/build -G Ninja \
  -DARCH=generic \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_GUI=OFF \
  -DPython3_EXECUTABLE=/usr/bin/python3
cmake --build ../nextpnr/build --target nextpnr-generic --parallel 12
```

The example below uses this executable directly; no system installation is needed.

## Map, route and generate the NPU bitstream

The SoC RTL is a separate repository. Use its **`OWAS130` branch** for this
example. If needed, clone it into the example's source directory:

```bash
git clone --branch OWAS130 --recurse-submodules \
  git@github.com:NeverInControl/CrocoScale_SoC.git \
  demo_CrocoScale_OWAS/CrocoScale_SoC
```

Provide the RTL files, design top, result directory and the fabric's three
nextpnr model files. For this NPU, also provide `custom_prims.v` and
**`fabulous_top_wrapper.v`**: the wrapper defines the peripheral BEL connections,
locations and global clock. It is merged after mapping the design RTL.

Run this complete example from this repository's root. It uses 12 mapping workers,
a 300-second selection budget, LUT4 source synthesis and a reported capacity of
1,152 FLUTs. Equivalence checking is enabled by default.

```bash
source .venv/bin/activate

NPU_RTL="demo_CrocoScale_OWAS/CrocoScale_SoC/SOFT_LOGIC/full"
FABRIC="OWAS_fabric"
RESULTS="demo_CrocoScale_OWAS/npu_runs/npu_$(date -u +%Y%m%dT%H%M%SZ)"

task fab_mapper -- \
  "$NPU_RTL/*.sv" \
  --top-module npu_full_controller \
  --results-dir "$RESULTS" \
  --bel-v3-file "$FABRIC/.FABulous/bel.v3.txt" \
  --pips-file "$FABRIC/.FABulous/pips.txt" \
  --placement-estimate-file "$FABRIC/.FABulous/placement_estimate.txt" \
  --custom-primitives "$FABRIC/user_design/custom_prims.v" \
  --merge-top-wrapper "$NPU_RTL/fabulous_top_wrapper.v" \
  --workers 12 \
  --selection-seconds 300 \
  --source-lut-size 4 \
  --capacity 1152 \
  --nextpnr-executable ../nextpnr/build/nextpnr-generic \
&& task bitstream \
  FASM="$RESULTS/routing/design.fasm" \
  BITSTREAM_SPEC="$FABRIC/.FABulous/bitStreamSpec.bin" \
  OUTPUT="$RESULTS/routing/design.bin"
```

The `&&` runs bitstream generation only after mapping, equivalence and routing
succeed. The specification comes from the same fabric used for routing, and the
binary lands at **`$RESULTS/routing/design.bin`**. Use
`task fab_mapper -- --help` for all mapper options.

Each run creates:

```text
demo_CrocoScale_OWAS/npu_runs/npu_<timestamp>/
├── mapping/<timestamp>/    # Netlists, mapping IR, settings and progress/report files
└── routing/
    ├── design.fasm
    ├── design.bin          # Generated binary bitstream
    ├── nextpnr.log
    ├── commands.log
    └── summary.rpt
```

## Regenerate a bitstream from an existing run

Set `RESULTS` to the completed run directory, then run:

```bash
FABRIC="OWAS_fabric"
task bitstream \
  FASM="$RESULTS/routing/design.fasm" \
  BITSTREAM_SPEC="$FABRIC/.FABulous/bitStreamSpec.bin" \
  OUTPUT="$RESULTS/routing/design.bin"
```

Use the bitstream specification matching that run's fabric.
