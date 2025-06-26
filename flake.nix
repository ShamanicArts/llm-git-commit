{
  description = "a plugin for SimonW llm CLI which analyses diffs in a local git repository , generates commit messages in an interactive prompt & commits";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = {
    self,
    nixpkgs,
    ...
  }: let
    inherit (self) outputs;
    systems = [
      "x86_64-linux"
      "aarch64-linux"
      "x86_64-darwin"
      "aarch64-darwin"
    ];
    forAllSystems = nixpkgs.lib.genAttrs systems;
  in {
    packages = forAllSystems (system: import ./Nix/Packages nixpkgs.legacyPackages.${system});

    formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.alejandra);

    devShell = forAllSystems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      myPython = pkgs.python3;
      pythonWithPkgs = myPython.withPackages (ps: [
        ps.pip
        ps.setuptools
      ]);
      venv = "venv";
    in
      pkgs.mkShell {
        packages = [
          pythonWithPkgs
        ];

        shellHook = ''
          python3 -m venv venv
          source venv/bin/activate
          pip install -e .
        '';
      });
  };
}
