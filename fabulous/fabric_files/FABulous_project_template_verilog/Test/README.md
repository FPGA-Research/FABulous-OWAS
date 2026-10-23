# FABulous simulation

This assumes FABulous is installed properly and the default instructions were followed to build the default fabric.
FABulous provides a simulation environment to test the fabric and the bitstream generated for it.
For simple use cases, there is the `run_simulation command` in the FABulous shell.
For more complex use cases it can be useful to create an own flow, like the following example `make` based flow.


Please make sure to use recent versions of (Yosys)[https://github.com/YosysHQ/yosys], (nextpnr-generic)[https://github.com/YosysHQ/nextpnr] (_not_ the old FABulous nextpnr fork)
and (iverilog)[https://github.com/steveicarus/iverilog] or use the (OSS-CAD-Suite)[https://github.com/YosysHQ/oss-cad-suite-build] which provides nightly builds of the necessary dependencies.

Also, make sure you have the `make` package installed:
```
$ sudo apt-get install make
```

Type `make build_test_design` to create the bitstream and `make run_simulation` to compare a simulation
of the fabric running the bitstream against the design.

Other useful make targets are:
- `make` or `make sim` to build the bitstream, run simulation and remove all generated files afterward.
- `make clean` to remove all generated files
- `make build_test_design` to build the bitstream
- `make run_simulation` to run the simulation
- `make run_FABulous_demo` to run the default FABulous flow
- `make run_GTKWave` to run the GTKWave waveform viewer with the generated simulation waveform

Take a look into the Makefile to build your own flow.

## SPI configuration port

With `ConfigInterface,SPI` in `fabric.csv`, the fabric is configured over SPI
(`SPI_SCLK`, `SPI_CS_N`, `SPI_MOSI`, `SPI_MISO`) instead of the UART `Rx`.
The Taskfile and the Makefile detect the setting and compile the testbenches
with `-DCONFIG_SPI`, so `sequential_16bit_en_tb` connects the SPI ports (held
idle) and still loads the bitstream through the parallel port.

`task fab-sim-spi` runs the full cycle with `sequential_16bit_en_spi_tb`
instead, which sends the bitstream over SPI (mode 1, MSB first, whole 32 bit
words). It refuses to run when `fabric.csv` selects the UART.

## Simulating with Vivado xsim

`task run-simulation SIMULATOR=xvlog` runs the same testbench under AMD
Vivado's xsim, and `task fab-sim SIMULATOR=xvlog` wraps it in the full
build-fabric, build-design, simulate, clean cycle. It needs `xvlog`, `xelab`
and `xsim` on `PATH` from a Vivado installation; nothing else in the flow
changes.

The value of the xsim path is the analysis mode, not the simulator. xvlog reads
the fabric and the user design as IEEE 1364-2005 Verilog, whereas the Icarus
flow uses `iverilog -g2012`, so constructs that are legal only in
SystemVerilog fail here and pass there. The testbench is exempt and compiles
with `-sv`, because it uses `$fatal` and an unsized array bound.

Two behaviours are worth knowing. xsim writes VCD and has no FST writer, so
`WAVEFORM_TYPE` does not apply and the waveform lands at
`build/<design>_xsim.vcd`. And xsim exits 0 even after `$fatal`, so the task
greps its log for a fatal report and fails on that instead of trusting the exit
status.

If `xelab` stops at `cannot find crt1.o`, its linker is not picking up the host
C runtime; point it at the directory holding those objects, for example
`LIBRARY_PATH=/usr/lib/x86_64-linux-gnu task run-simulation SIMULATOR=xvlog`.
