"""Tests for the serial configuration ports of the generated top wrapper."""

import re
import subprocess
from pathlib import Path

import pytest

from fabulous.custom_exception import InvalidFabricParameter
from fabulous.fabric_definition.define import ConfigInterface
from fabulous.fabric_definition.fabric import Fabric
from fabulous.fabric_generator.code_generator.code_generator_Verilog import (
    VerilogCodeGenerator,
)
from fabulous.fabric_generator.code_generator.code_generator_VHDL import (
    VHDLCodeGenerator,
)
from fabulous.fabric_generator.gen_fabric.gen_top_wrapper import generateTopWrapper
from fabulous.fabulous_repl.fabulous_repl import FABulousREPL
from fabulous.fabulous_settings import get_context, init_context
from tests.conftest import make_empty_tile, make_fabric_from_grid, run_cmd

SPI_PORTS = ["SPI_SCLK", "SPI_CS_N", "SPI_MOSI", "SPI_MISO"]


def _fabric(config_interface: ConfigInterface) -> Fabric:
    """Return a small 3x2 fabric using the given configuration interface.

    Parameters
    ----------
    config_interface : ConfigInterface
        Serial configuration interface of the top wrapper.

    Returns
    -------
    Fabric
        A real fabric with config-free border rows.
    """
    grid = [
        [make_empty_tile(f"T{y}_{x}", config_bits=bits) for x in range(2)]
        for y, bits in enumerate([0, 8, 0])
    ]
    fabric = make_fabric_from_grid(grid)
    fabric.config_interface = config_interface
    return fabric


def _top_ports(rtl: str) -> set[str]:
    """Return the port names declared on the `eFPGA_top` module.

    Parameters
    ----------
    rtl : str
        Generated top wrapper Verilog.

    Returns
    -------
    set[str]
        Names of all ports in the module header.
    """
    header = rtl[rtl.index("module eFPGA_top") : rtl.index(");")]
    return set(re.findall(r"\b(?:input|output)\b[^;,\n]*?\b(\w+)\s*(?:,|\n|$)", header))


def _config_instance_ports(rtl: str) -> set[str]:
    """Return the port names connected on the `eFPGA_Config` instance.

    Parameters
    ----------
    rtl : str
        Generated top wrapper Verilog.

    Returns
    -------
    set[str]
        Names of all ports in the instance's port list.
    """
    start = rtl.index("eFPGA_Config_inst")
    return set(re.findall(r"\.(\w+)\s*\(", rtl[start : rtl.index(");", start)]))


@pytest.mark.parametrize(
    ("config_interface", "present", "absent"),
    [
        (ConfigInterface.UART, ["Rx"], SPI_PORTS),
        (ConfigInterface.SPI, SPI_PORTS, ["Rx"]),
    ],
)
def test_serial_config_ports(
    tmp_path: Path,
    config_interface: ConfigInterface,
    present: list[str],
    absent: list[str],
) -> None:
    """The top and the `eFPGA_Config` instance carry only the selected ports."""
    writer = VerilogCodeGenerator()
    writer.outFileName = tmp_path / "eFPGA_top.v"
    generateTopWrapper(writer, _fabric(config_interface))
    rtl = writer.outFileName.read_text()

    top = _top_ports(rtl)
    instance = _config_instance_ports(rtl)
    for port in [*present, "ComActive", "ReceiveLED", "s_clk", "s_data"]:
        assert port in top
        assert port in instance
    for port in absent:
        assert port not in top
        assert port not in instance
    spi_param = '.ConfigInterface("SPI")' in rtl
    assert spi_param is (config_interface == ConfigInterface.SPI)


def test_spi_rejects_vhdl(tmp_path: Path) -> None:
    """The VHDL `eFPGA_Config` has no SPI receiver, so SPI is refused early."""
    writer = VHDLCodeGenerator()
    writer.outFileName = tmp_path / "eFPGA_top.vhdl"
    with pytest.raises(InvalidFabricParameter, match="SPI"):
        generateTopWrapper(writer, _fabric(ConfigInterface.SPI))
    assert not writer.outFileName.exists()


@pytest.mark.slow
@pytest.mark.parametrize(
    ("value", "used", "unused"),
    [
        ("UART", "config_UART", "fabric_spi_receiver"),
        ("SPI", "fabric_spi_receiver", "config_UART"),
    ],
)
def test_template_project_elaborates(
    fabulous_project: Path, tmp_path: Path, value: str, used: str, unused: str
) -> None:
    """The template's eFPGA_Config matches the generated top in both modes."""
    csv = fabulous_project / "fabric.csv"
    lines = [
        line
        for line in csv.read_text().splitlines(keepends=True)
        if not line.startswith("ConfigInterface")
    ]
    csv.write_text(
        "".join(lines).replace(
            "ParametersBegin,", f"ParametersBegin,\nConfigInterface,{value},", 1
        )
    )
    init_context(fabulous_project)
    cli = FABulousREPL(
        "verilog", force=False, interactive=False, verbose=False, debug=True
    )
    run_cmd(cli, "load_fabric")
    run_cmd(cli, "run_fab")

    # Flattened by file name like the project's Test/Taskfile copy-files:
    # tiles share BEL files (e.g. Config_access.v) that must be read once.
    sources = {
        path.name: path
        for path in [
            *sorted((fabulous_project / "Tile").rglob("*.v")),
            *sorted((fabulous_project / "Fabric").glob("*.v")),
        ]
    }
    compiled = tmp_path / "top.vvp"
    result = subprocess.run(
        [
            str(get_context().iverilog_path),
            "-g2012",
            "-s",
            "eFPGA_top",
            "-o",
            str(compiled),
            *map(str, sources.values()),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    # vvp lists every instantiated scope with its module name
    netlist = compiled.read_text()
    assert f'"{used}"' in netlist
    assert f'"{unused}"' not in netlist
