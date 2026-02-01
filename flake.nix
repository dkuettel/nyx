{
  description = "TODO";

  inputs = {
    nixpkgs.url = "github:dkuettel/nixpkgs/stable";
    flake-utils.url = "github:numtide/flake-utils";

    # see https://pyproject-nix.github.io/

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        name = "TODO";

        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };
        inherit (pkgs) lib;
        inherit (builtins) map;

        python = pkgs.python314;

        uv = pkgs.writeScriptBin "uv" ''
          #!${pkgs.zsh}/bin/zsh
          set -eu -o pipefail
          UV_PYTHON=${python}/bin/python ${pkgs.uv}/bin/uv --no-python-downloads $@
        '';
        # for pyproject.toml
        #   [tool.uv.build-backend]
        #   namespace = true  # if you use namespace packages
        #   [project.scripts]
        #   some = "some.main:app"  # for executable entry points
        #   [tool.hatch.build.targets.wheel]
        #   packages = ["src/some.py"]  # if you use single files, but needs old build system below
        #   [build-system]
        #   requires = ["hatchling"]
        #   build-backend = "hatchling.build"

        prodPkgs = # with pkgs;
          [ ];

        devPkgs = (
          [
            uv
            python
          ]
          ++ (with pkgs; [
            ruff
            basedpyright
            nil # nix language server
            nixfmt-rfc-style # nixpkgs-fmt is deprecated
          ])
        );

        devLibs = with pkgs; [
          stdenv.cc.cc
          # zlib
          # libglvnd
          # xorg.libX11
          # glib
          # eigen
        ];

        devLdLibs = pkgs.buildEnv {
          name = "${name}-dev-ld-libs";
          paths = map (lib.getOutput "lib") devLibs;
        };

        devEnv = pkgs.buildEnv {
          name = "${name}-dev-env";
          paths = devPkgs ++ devLibs ++ prodPkgs;
        };

        pyproject = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
        moduleOverrides =
          final: prev:
          # let
          #   # see https://github.com/TyberiusPrime/uv2nix_hammer_overrides/tree/main
          #   # I dont fully understand what we do here, we switch to setuptools instead of wheels?
          #   # for libs that need to build for nix? and we might have to add build dependencies?
          #   setuptools =
          #     prev_lib:
          #     prev_lib.overrideAttrs (old: {
          #       nativeBuildInputs =
          #         (old.nativeBuildInputs or [ ]) ++ (final.resolveBuildSystem { setuptools = [ ]; });
          #     });
          # in
          {
            # pprofile = setuptools prev.pprofile;
          };
        modules =
          (pkgs.callPackage pyproject-nix.build.packages {
            python = python;
          }).overrideScope
            (
              lib.composeManyExtensions [
                pyproject-build-systems.overlays.default
                (pyproject.mkPyprojectOverlay { sourcePreference = "wheel"; })
                moduleOverrides
              ]
            );
        venv = modules.mkVirtualEnv "${name}-venv" pyproject.deps.default;
        inherit (pkgs.callPackages pyproject-nix.build.util { }) mkApplication;
        app = mkApplication {
          venv = venv;
          package = modules.TODO;
        };
        # TODO this could help, but Im not sure its the best way to do it
        # wrappedApp = pkgs.writeScriptBin "TODO" ''
        #   #!${pkgs.zsh}/bin/zsh
        #   LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/run/opengl-driver/lib/ ${app}/bin/TODO $@
        # '';
        package = pkgs.buildEnv {
          name = "${name}-env";
          paths = [ app ] ++ prodPkgs;
          postBuild = ''
            # TODO for example add some $out/share/zsh/site-functions/_name for completions
          '';
        };

      in
      {
        packages.default = package;
        devShells.default = pkgs.mkShellNoCC {
          packages = [ devEnv ];
          # TODO opengl is not always needed
          LD_LIBRARY_PATH = "/run/opengl-driver/lib/:${pkgs.lib.makeLibraryPath [ devLdLibs ]}";
          shellHook = ''
            if [[ -v h ]]; then
              export PATH=$h/bin:$PATH;
              if [[ ! $h/.nd/state -ef $h/.nd/dev ]] then
                # something
                cp -d $h/.nd/dev $h/.nd/state
              fi
            else
              echo 'Project root env var h is not set.' >&2
            fi
          '';
        };
      }
    );
}
