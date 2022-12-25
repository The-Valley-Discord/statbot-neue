with (import (import ./pinned-nixpkgs.nix) { });

python310Packages.buildPythonPackage {
  src = builtins.path {
    path = ./.;
    name = "statbot";
  };

  pname = "statbot";
  version = "0.0.0";

  propagatedBuildInputs =
    (with python310Packages; [ discordpy setuptools matplotlib ]);
  format = "pyproject";
}
