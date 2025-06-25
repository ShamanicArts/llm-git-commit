{
  python3Packages,
  pkgs,
  lib,
  ...
}:
python3Packages.buildPythonApplication rec {
  name = "llm-git-commit";
  version = "0.1.4";
  pyproject = true;

  src = ../../dist/llm_git_commit-0.1.1.tar.gz;

  doCheck = false;

  build-system = with pkgs.python3Packages; [
    setuptools
  ];

  dependencies = with pkgs.python3Packages; [
    click
    llm
    prompt-toolkit
  ];

  dontCheckRuntimeDeps = true;

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
