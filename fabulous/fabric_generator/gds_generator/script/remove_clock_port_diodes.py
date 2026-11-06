"""OpenDB script to remove port diodes from the clock port nets.

A diode on a clock net that feeds a nested clock tree crashes the TritonCTS
latency balancer.
"""

from typing import Any

import click
import odb
from librelane.logging.logger import info
from librelane.scripts.odbpy.reader import click_odb


@click.option(
    "--clock-port",
    "clock_ports",
    type=str,
    multiple=True,
    help="Clock port name. Repeat the option for multiple ports.",
)
@click.option("--diode-cell", required=True, type=str, help="Diode cell name.")
@click.command()
@click_odb
def remove_clock_port_diodes(
    reader: Any,  # noqa: ANN401
    clock_ports: tuple[str, ...],
    diode_cell: str,
) -> None:
    """Remove diode cells connected to the clock port nets."""
    for port in clock_ports:
        bterm = reader.block.findBTerm(port)
        if bterm is None or bterm.getNet() is None:
            info(f"Clock port '{port}' not found, skipping.")
            continue
        net = bterm.getNet()
        diodes = [
            it.getInst()
            for it in net.getITerms()
            if it.getInst().getMaster().getName() == diode_cell
        ]
        for inst in diodes:
            info(f"Removing diode '{inst.getName()}' from clock net '{net.getName()}'.")
            odb.dbInst.destroy(inst)


if __name__ == "__main__":
    remove_clock_port_diodes()
