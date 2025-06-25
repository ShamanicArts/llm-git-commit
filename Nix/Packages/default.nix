pkgs: rec {
  llm-git-commit = pkgs.python3.callPackage ./llm-git-commit.nix {};
  default = llm-git-commit;
}
