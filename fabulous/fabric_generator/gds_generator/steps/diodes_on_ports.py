"""FABulous GDS Generator - Diodes on Ports step."""

from importlib import resources

from librelane.logging.logger import info
from librelane.state.state import State
from librelane.steps.odb import OdbpyStep, PortDiodePlacement
from librelane.steps.openroad import DetailedPlacement, GlobalPlacement
from librelane.steps.step import CompositeStep, MetricsUpdate, Step, ViewsUpdate


@Step.factory.register()
class RemoveClockPortDiodes(OdbpyStep):
    """Remove the port diodes from the clock port nets."""

    id = "FABulous.RemoveClockPortDiodes"
    name = "Remove Clock Port Diodes"

    def get_script_path(self) -> str:
        """Get the path to the diode removal script."""
        return str(
            resources.files("fabulous.fabric_generator.gds_generator.script")
            / "remove_clock_port_diodes.py"
        )

    def get_command(self) -> list[str]:
        """Pass the clock ports and the diode cell to the script."""
        clock_ports = self.config["CLOCK_PORT"] or []
        if isinstance(clock_ports, str):
            clock_ports = [clock_ports]
        args = ["--diode-cell", self.config["DIODE_CELL"].split("/")[0]]
        for port in clock_ports:
            args += ["--clock-port", port]
        return super().get_command() + args


@Step.factory.register()
class FABulousDiodesOnPorts(CompositeStep):
    """Insert diodes on design ports and legalize via global + detailed placement.

    Mirrors `Odb.DiodesOnPorts` but omits the GlobalRouting re-run after
    placement, since global routing is run at a separate step later in the flow.
    """

    id = "FABulous.DiodesOnPorts"
    name = "FABulous Diodes on Ports"

    Steps = [
        PortDiodePlacement,
        RemoveClockPortDiodes,
        GlobalPlacement,
        DetailedPlacement,
    ]

    def run(self, state_in: State, **kwargs: dict) -> tuple[ViewsUpdate, MetricsUpdate]:
        """Run the step if diodes on ports are configured and a diode cell is set."""
        if self.config["DIODE_ON_PORTS"] == "none":
            info(f"'DIODE_ON_PORTS' is set to 'none': skipping '{self.id}'...")
            return {}, {}
        if self.config["DIODE_CELL"] is None:
            raise ValueError(f"'DIODE_CELL' not set but '{self.id}' is enabled.")
        return super().run(state_in, **kwargs)
