{
  lib,
  stdenvNoCC,
  fetchFromGitHub,
  python3,
  bash,
  makeWrapper,
  versionCheckHook,
}:

let
  python = python3.withPackages (ps: [ ps.requests ]);
in
stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "cyberwatch-agent";
  version = "4.21";

  src = fetchFromGitHub {
    owner = "liberodark";
    repo = "cyberwatch-nixos";
    tag = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  sourceRoot = "${finalAttrs.src.name}/cyberwatch-agent";

  nativeBuildInputs = [ makeWrapper ];

  strictDeps = true;
  dontConfigure = true;
  dontBuild = true;

  postPatch = ''
    substituteInPlace cyberwatch_agent/system_command.py \
      --replace-fail "['/bin/bash']" "['${lib.getExe bash}']"
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out/share/cyberwatch-agent $out/bin
    cp cyberwatch-agent.py $out/share/cyberwatch-agent/
    cp -r cyberwatch_agent $out/share/cyberwatch-agent/

    ${python.interpreter} -m compileall -q $out/share/cyberwatch-agent

    makeWrapper ${python.interpreter} $out/bin/cyberwatch-agent \
      --add-flags "$out/share/cyberwatch-agent/cyberwatch-agent.py"

    runHook postInstall
  '';

  nativeInstallCheckInputs = [ versionCheckHook ];
  versionCheckProgramArg = "--version";
  doInstallCheck = true;

  meta = {
    description = "Cyberwatch Agent";
    homepage = "https://www.cyberwatch.fr/";
    license = lib.licenses.unfree;
    maintainers = with lib.maintainers; [ liberodark ];
    platforms = lib.platforms.linux;
    mainProgram = "cyberwatch-agent";
  };
})
