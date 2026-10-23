# FAB-mapper (`sat-fab-flut5`): FLUT5 mapping, equivalence checking and routing.
# Built from its own uv.lock as a separate uv2nix workspace, so its pinned
# dependencies (ortools, pyosys, ...) never mix with FABulous's venv. Only the
# entry point is exposed; putting the venv's bin/ on PATH would shadow the
# FABulous python, pytest, etc.
{
  lib,
  pkgs,
  python,
  pyproject-nix,
  uv2nix,
  pyproject-build-systems,
  src,
  nextpnr,
}:
let
  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = src; };

  pythonSet =
    (pkgs.callPackage pyproject-nix.build.packages {
      inherit python;
    }).overrideScope
      (
        lib.composeManyExtensions [
          pyproject-build-systems.overlays.wheel
          (workspace.mkPyprojectOverlay { sourcePreference = "wheel"; })
        ]
      );

  virtualenv = pythonSet.mkVirtualEnv "fab-mapper-env" workspace.deps.default;
in
pkgs.runCommand "fab-mapper"
  {
    nativeBuildInputs = [ pkgs.makeWrapper ];
    meta = {
      description = "FAB-mapper FLUT5 mapping and routing flow for FABulous fabrics";
      mainProgram = "sat-fab-flut5";
    };
  }
  ''
    mkdir -p $out/bin
    # The router resolves its default `nextpnr-generic` through PATH; prefer the
    # flake's pinned build, which carries the constant-driver pin fix.
    makeWrapper ${virtualenv}/bin/sat-fab-flut5 $out/bin/sat-fab-flut5 \
      --prefix PATH : ${lib.makeBinPath [ nextpnr ]}
  ''
