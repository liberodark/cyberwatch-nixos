{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.cyberwatch-agent;
  confDir = "/etc/cyberwatch-agent";
  confFile = "${confDir}/agent.conf";
  logDir = "/var/log/cyberwatch-agent";

  hasRegistrationKeys = cfg.registrationKeyIdFile != null;

  confTemplate = pkgs.writeText "cyberwatch-agent.conf" (
    lib.generators.toINI { } {
      api = {
        base_url = cfg.baseUrl;
        access_key_id = "";
        secret_access_key = "";
        registration_key_id = lib.optionalString hasRegistrationKeys "@registrationKeyId@";
        secret_registration_key = lib.optionalString hasRegistrationKeys "@secretRegistrationKey@";
        groups = lib.concatStringsSep "," cfg.groups;
        category = cfg.category;
        allow_selfsigned = cfg.allowSelfsigned;
      };
      proxy = {
        enabled = cfg.proxy != null;
        host = lib.optionalString (cfg.proxy != null) cfg.proxy;
      };
    }
  );

  seedScript = pkgs.writeShellScript "cyberwatch-agent-seed-conf" ''
    set -euo pipefail

    if [ -s ${confFile} ]; then
      exit 0
    fi

    install -m 0640 -o ${cfg.user} -g ${cfg.user} ${confTemplate} ${confFile}
    ${lib.optionalString hasRegistrationKeys ''
      ${lib.getExe pkgs.replace-secret} '@registrationKeyId@' '${cfg.registrationKeyIdFile}' ${confFile}
      ${lib.getExe pkgs.replace-secret} '@secretRegistrationKey@' '${cfg.secretRegistrationKeyFile}' ${confFile}
    ''}
  '';
in
{
  options.services.cyberwatch-agent = {
    enable = lib.mkEnableOption "the Cyberwatch vulnerability management agent";

    package = lib.mkPackageOption pkgs "cyberwatch-agent" { };

    baseUrl = lib.mkOption {
      type = lib.types.str;
      example = "https://cyberwatch.example.com/api/v2/";
      description = ''
        API URL of the Cyberwatch instance (`base_url` field of
        {file}`agent.conf`). Only used to seed the configuration on first
        start; later changes require removing {file}`/etc/cyberwatch-agent/agent.conf`
        or reconfiguring the agent with {command}`cyberwatch-agent set_config`.
      '';
    };

    registrationKeyIdFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      example = "/run/secrets/cyberwatch-registration-key-id";
      description = ''
        File containing the `registration_key_id` of an "agent installation"
        API key created in the Cyberwatch web interface. Read at runtime and
        never copied to the Nix store; only used while the asset is not
        registered yet.
      '';
    };

    secretRegistrationKeyFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      example = "/run/secrets/cyberwatch-secret-registration-key";
      description = "File containing the matching `secret_registration_key`.";
    };

    groups = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [
        "nixos"
        "production"
      ];
      description = "Cyberwatch groups assigned to the asset at registration time.";
    };

    category = lib.mkOption {
      type = lib.types.str;
      default = "server";
      description = "Asset category shown in the Cyberwatch inventory.";
    };

    allowSelfsigned = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Whether to accept a self-signed certificate on the Cyberwatch instance.";
    };

    proxy = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "https://user:pass@proxy:3128/";
      description = "HTTP(S) proxy used to reach the Cyberwatch API.";
    };

    user = lib.mkOption {
      type = lib.types.str;
      default = "root";
      description = ''
        User running the agent. Running as root matches the upstream package
        behavior; a restricted user requires additional sudo rules, see the
        Cyberwatch documentation ("run the agent as a different user").
      '';
    };

    interval = lib.mkOption {
      type = lib.types.ints.positive;
      default = 300;
      description = "Seconds between two agent runs (`OnUnitActiveSec` of the timer).";
    };

    extraScanPackages = lib.mkOption {
      type = lib.types.listOf lib.types.package;
      default = [ ];
      example = lib.literalExpression "[ pkgs.dmidecode pkgs.lsof ]";
      description = ''
        Extra packages exposed in the `PATH` of the scan scripts pushed to
        the agent by the Cyberwatch server.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = (cfg.registrationKeyIdFile == null) == (cfg.secretRegistrationKeyFile == null);
        message = "services.cyberwatch-agent: registrationKeyIdFile and secretRegistrationKeyFile must be set together.";
      }
    ];

    environment.systemPackages = [ cfg.package ];

    systemd.tmpfiles.rules = [
      "d ${confDir} 0750 ${cfg.user} ${cfg.user} -"
      "d ${logDir} 0750 ${cfg.user} ${cfg.user} -"
      "f ${logDir}/agent.log 0640 ${cfg.user} ${cfg.user} -"
    ];

    systemd.services.cyberwatch-agent = {
      description = "Cyberwatch agent";
      after = [
        "network-online.target"
        "time-sync.target"
      ];
      wants = [ "network-online.target" ];

      path = cfg.extraScanPackages ++ [
        "/run/current-system/sw"
        "/run/wrappers"
      ];

      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
        Group = cfg.user;
        ExecStart = lib.getExe cfg.package;
        ExecStartPre = "+${seedScript}";

        StandardOutput = "null";
        LockPersonality = true;
        ProtectClock = true;
        ProtectKernelLogs = true;
        ProtectKernelTunables = true;
        ProtectProc = "invisible";
        RestrictAddressFamilies = "AF_INET AF_INET6 AF_NETLINK AF_UNIX";
        ReadWritePaths = [
          "-/sys/fs/cgroup"
          "-/var/lib/containers/"
          "-/run/containers/"
        ];
      };
    };

    systemd.timers.cyberwatch-agent = {
      description = "Trigger the Cyberwatch agent every ${toString cfg.interval} seconds";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = 120;
        OnUnitActiveSec = cfg.interval;
      };
    };
  };
}
