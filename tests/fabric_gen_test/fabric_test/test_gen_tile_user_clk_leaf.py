"""Tests for the `USER_CLK_LEAF` tile option (UserCLK leaf buffers per BEL group)."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from fabulous.custom_exception import InvalidTileDefinition
from fabulous.fabric_definition.tile import Tile
from fabulous.fabric_generator.code_generator.code_generator import CodeGenerator
from fabulous.fabric_generator.gen_fabric.gen_tile import (
    generateTile,
    user_clk_bel_nets,
)
from fabulous.fabric_generator.parser.parse_csv import parseTilesCSV
from fabulous.fabulous_settings import init_context

# The template LUT4AB tile has eight clocked LUT BELs (LA_..LH_) followed by the
# unclocked MUX8LUT BEL.
LUT_PREFIXES = ["LA_", "LB_", "LC_", "LD_", "LE_", "LF_", "LG_", "LH_"]


def _lut4ab(project: Path, leaf_line: str | None) -> Tile:
    csv = project / "Tile" / "LUT4AB" / "LUT4AB.csv"
    if leaf_line is not None:
        csv.write_text(csv.read_text().replace("MATRIX,", f"{leaf_line}\nMATRIX,", 1))
    init_context(project)
    (tile,) = parseTilesCSV(csv)[0]
    return tile


def _bel_clocks(rtl: str) -> dict[str, str]:
    """Map each BEL instance prefix to the net on its UserCLK pin."""
    clocks = {}
    for m in re.finditer(r"Inst_(\w+?_)\w*\s*\((.*?)\);", rtl, re.DOTALL):
        clk = re.search(r"\.UserCLK\((\w+)\)", m[2])
        if clk:
            clocks[m[1]] = clk[1]
    return clocks


def _generate(
    tile: Tile, factory: Callable[[str, str], CodeGenerator], **kwargs: bool
) -> str:
    writer = factory(".v", tile.name)
    generateTile(writer, tile, **kwargs)
    return writer.outFileName.read_text()


@pytest.mark.parametrize(
    ("bels_per_leaf", "expected_leaf"),
    [
        (4, [0, 0, 0, 0, 1, 1, 1, 1]),
        (3, [0, 0, 0, 1, 1, 1, 2, 2]),
        (8, [0] * 8),
    ],
)
def test_bels_grouped_onto_leaf_buffers(
    project: Path,
    code_generator_factory: Callable[[str, str], CodeGenerator],
    bels_per_leaf: int,
    expected_leaf: list[int],
) -> None:
    """UserCLK BELs are grouped in CSV order, one `clk_leaf_buf` per group."""
    tile = _lut4ab(project, f"USER_CLK_LEAF,{bels_per_leaf}")
    assert tile.user_clk_leaf_bels == bels_per_leaf

    rtl = _generate(tile, code_generator_factory)

    clocks = _bel_clocks(rtl)
    assert [clocks[p] for p in LUT_PREFIXES] == [
        f"UserCLK_leaf{i}" for i in expected_leaf
    ]
    n_leaf = max(expected_leaf) + 1
    for i in range(n_leaf):
        assert f"wire UserCLK_leaf{i};" in rtl
        assert re.search(
            rf"clk_leaf_buf inst_clk_leaf{i}\s*\(\s*\.A\(UserCLK\),\s*"
            rf"\.X\(UserCLK_leaf{i}\)",
            rtl,
        )
    assert rtl.count("clk_leaf_buf inst_clk_leaf") == n_leaf
    assert re.search(r"clk_buf inst_clk_buf\s*\(\s*\.A\(UserCLK\)", rtl)


def test_without_option_bels_use_user_clk_directly(
    project: Path, code_generator_factory: Callable[[str, str], CodeGenerator]
) -> None:
    """Without `USER_CLK_LEAF` the generated tile is unchanged."""
    tile = _lut4ab(project, None)
    assert tile.user_clk_leaf_bels is None

    rtl = _generate(tile, code_generator_factory)

    assert set(_bel_clocks(rtl).values()) == {"UserCLK"}
    assert "clk_leaf_buf" not in rtl


def test_disable_user_clk_skips_leaf_buffers(project: Path) -> None:
    """With UserCLK disabled no BEL gets a clock net and no leaf is needed."""
    tile = _lut4ab(project, "USER_CLK_LEAF,4")
    assert user_clk_bel_nets(tile, disable_user_clk=True) == [None] * len(tile.bels)


@pytest.mark.parametrize("value", ["0", "-1", "x", ""])
def test_invalid_value_raises(project: Path, value: str) -> None:
    """The BEL count must be a positive integer."""
    with pytest.raises(InvalidTileDefinition, match="USER_CLK_LEAF"):
        _lut4ab(project, f"USER_CLK_LEAF,{value}")


def test_duplicate_raises(project: Path) -> None:
    """`USER_CLK_LEAF` may appear only once per tile."""
    with pytest.raises(InvalidTileDefinition, match="more than once"):
        _lut4ab(project, "USER_CLK_LEAF,4\nUSER_CLK_LEAF,2")


def test_tile_without_clocked_bel_raises(project: Path) -> None:
    """`USER_CLK_LEAF` on a tile without UserCLK BELs is a definition error."""
    csv = project / "Tile" / "N_term_single" / "N_term_single.csv"
    csv.write_text(csv.read_text().replace("MATRIX,", "USER_CLK_LEAF,4\nMATRIX,", 1))
    init_context(project)
    with pytest.raises(InvalidTileDefinition, match="none of its BELs"):
        parseTilesCSV(csv)
