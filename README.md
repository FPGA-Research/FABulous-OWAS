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

> [!IMPORTANT]
> The `fabulous-bit-gen` dependency comes from the private
> `FPGA-Research/FABulous-bit-gen-OWAS` repository (you need read access to it)
> and is pinned by its HTTPS URL. Without credentials for it, `uv sync` fails with `could not read Username
> for 'https://github.com'`.
>
> Skip this step if you access GitHub over HTTPS with `gh auth setup-git` or a
> token. The rewrite would switch that repository to SSH and break fetching it
> without an SSH key. Otherwise, run this once per machine so git fetches that
> repository over SSH:
>
> ```bash
> git config --global \
>   url."git@github.com:FPGA-Research/FABulous-bit-gen-OWAS".insteadOf \
>   "https://github.com/FPGA-Research/FABulous-bit-gen-OWAS"
> ```

Install `uv`, then run from this repository's root:

```bash
uv sync
source .venv/bin/activate
```

This also makes `task` available. SSH access to `FPGA-Research/FAB-mapper` is
required: `task fab_mapper` runs it through `uvx` in a separate cached environment
and checks for upstream updates. Push mapper changes to GitHub before running
this task to use them.

Routing needs upstream [nextpnr](https://github.com/YosysHQ/nextpnr): its fix for
the FABulous constant-driver pin directions, which can cause Router2 to fail, is
not in a release yet. Inside `nix develop`, `nextpnr-generic` is already on `PATH`.
Otherwise, build it in this repository using system build tools, outside the OSS
CAD Suite environment. The build needs CMake, Ninja, a C++17 compiler, Boost,
Eigen3 and Python development headers.

```bash
task nextpnr
```

This clones and builds `nextpnr/build/nextpnr-generic`. The example below uses
this executable directly; no system installation is needed.

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

Routing defaults to timing-driven SA/Router2 with **8 threads** and a **1 MHz**
clock target. Set `--freq` in MHz to change the target, for example `--freq 10`.
Routing can succeed without usable fabric timing information, but then nextpnr
cannot verify that the clock target is met.

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
  --freq 1 \
  --nextpnr-executable nextpnr/build/nextpnr-generic \
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
