{
  python3Packages,
  pkgs,
  lib,
}: let
  fs = lib.fileset;
  sourceFiles = fs.difference ../../. ../../dist;
in
  fs.trace sourceFiles
  python3Packages.buildPythonPackage rec {
    pname = "llm_git_commit";
    version = "0.1.4";
    pyproject = true;

    src = fs.toSource {
      root = ../../.;
      fileset = sourceFiles;
    };

    build-system = with pkgs.python3Packages; [
      setuptools
    ];

    dependencies = with pkgs.python3Packages; [
      click
      llm
      prompt-toolkit
    ];

    doCheck = true;

    pythonImportsCheck = ["llm_git_commit"];

    meta = with lib; {
      description = ''
        a plugin for SimonW llm CLI which analyses diffs in a local git repository , generates commit messages in an interactive prompt & commits
      '';
      homepage = "https://github.com/ShamanicArts/llm-git-commit.git";
      license = licenses.mit;
      maintainers = with maintainers; [Immelancholy];
      mainProgram = "llm-git-commit";
    };
  }
