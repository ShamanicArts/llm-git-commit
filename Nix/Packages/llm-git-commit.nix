{
  python3Packages,
  pkgs,
  lib,
  ...
}: let
  fs = lib.fileset;
  sourceFiles = ../../.;
in
  fs.trace sourceFiles
  python3Packages.buildPythonApplication {
    name = "llm-git-commit";
    version = "0.1.4";
    pyproject = true;
    src = fs.toSource {
      root = ../../.;
      fileset = sourceFiles;
    };

    nativeBuildInputs = with pkgs.python3Packages; [
      setuptools
      wheel
    ];

    propagatedBuildInputs = with pkgs.python3Packages; [
      click
      llm
      prompt-toolkit
    ];

    meta = with lib; {
      description = ''
        a plugin for SimonW llm CLI which analyses diffs in a local git repository , generates commit messages in an interactive prompt & commits
      '';
      homepage = "https://github.com/ShamanicArts/llm-git-commit.git";
      license = licenses.mit;
      maintainers = with maintainers; [Immelancholy];
    };
  }
