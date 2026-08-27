#!/usr/bin/env python3
# coding: utf-8

import os.path
import sys
import locale

try:
    import pwd
except ImportError:
    pass


class Checks(object):
    def __init__(self, environs):
        self.env = environs
        self.conf = None
        self.logger = None
        self.system_command = None
        self.api_client = None

    def check(self, mode):
        if mode in ['all', 'env']:
            self.environment()
            self.installation()

        if mode in ['all', 'conf']:
            self.config()

        if mode in ['all', 'logging']:
            self.logging()

        if mode in ['all', 'api']:
            self.api_connectivity()

        if mode in ['all', 'deploy']:
            self.command_deployment()

    def environment(self):
        print(u'{[ Environment ]}')
        print(u'Operating System: {0}'.format(self.env.os))
        print(u'Package Manager: {0}'.format(self.env.os.PackageManager))
        print(u'')
        print(u'Encoding: sys.stdout: {0}'.format(sys.stdout.encoding))
        print(u'Encoding: sys.stdin : {0}'.format(sys.stdin.encoding))
        print(u'Encoding: locale    : {0}'.format(locale.getpreferredencoding()))
        print(u'Encoding: filesystem: {0}'.format(sys.getfilesystemencoding()))
        print(u'Encoding: default   : {0}'.format(sys.getdefaultencoding()))
        print(u'')

    def installation(self):
        print(u'{[ Installation ]}')
        print(u'App path: {0}'.format(self.env.app_path))
        print(u'Config path: {0}'.format(self.env.config_path))
        print(u'Config path: Exists? {0} - Readable? {1} - Writable? {2}'.format(
            Checks.is_file(self.env.config_path),
            Checks.is_readable(self.env.config_path),
            Checks.is_writable(self.env.config_path)
        ))
        print(u'Log dir: {0}'.format(self.env.logs_path))
        print(u'Log dir: Exists? {0} - Readable? {1} - Writable? {2}'.format(
            Checks.is_dir(self.env.logs_path),
            Checks.is_readable(self.env.logs_path),
            Checks.is_writable(self.env.logs_path)
        ))
        print(u'Log file: {0}'.format(self.env.logs_file))
        print(u'Log file: Exists? {0} - Readable? {1} - Writable? {2}'.format(
            Checks.is_file(self.env.logs_file),
            Checks.is_readable(self.env.logs_file),
            Checks.is_writable(self.env.logs_file)
        ))
        print(u'')

    def config(self):
        print(u'{[ Configuration ]}')

        from .configuration import Configuration
        self.conf = Configuration(self.env).load()

        if not self.conf:
            print(u'Failed to load configuration...')
            return

        print(u'seems valid? {0}'.format(self.conf.is_valid()))
        print(u'seems registered? {0}'.format(self.conf.is_registered()))

        print(u'api.base_url: {0}'.format(self.conf.api.base_url))
        print(u'api.access_key_id: {0}'.format(self.conf.api.access_key_id))
        print(u'api.secret_access_key.length: {0}'
              .format(len(self.conf.api.secret_access_key)))
        print(u'api.allow_selfsigned: {0}'.format(self.conf.api.allow_selfsigned))
        print(u'proxy.enabled: {0}'.format(self.conf.proxy.enabled))
        print(u'proxy.host: {0}'.format(self.conf.proxy.hosts['http']))
        if self.env.os.Windows:
            print(u'wsus_proxy.enabled: {0}'.format(self.conf.wsus_proxy.enabled))
            print(u'wsus_proxy.host: {0}'.format(self.conf.wsus_proxy.host))
        print(u'')

    def logging(self):
        print(u'{[ Logger ]}')

        from .logger import Logger
        try:
            self.logger = Logger(self.env, debug=True).root_logger

            if not self.logger:
                print(u'Failed to load logger...')

            self.logger.debug(u'Debug Message')
            self.logger.info(u'Info Message')
            self.logger.warning(u'Warning Message')
            self.logger.error(u'Error Message')
            self.logger.critical(u'Critical Message')
        except Exception as e:
            print(u'CheckError: {0}'.format(str(e)))
        print(u'')

    def api_connectivity(self):
        print(u'{[ API Connectivity ]}')

        if not self.conf:
            print(u'Loading configuration...')
            from .configuration import Configuration
            self.conf = Configuration(self.env).load()

        from .api_client import ApiClient
        self.api_client = ApiClient(self.conf, self.logger)

        if not self.api_client:
            print(u'Failed to load API client...')
            return

        print(u'Ping: {0}'.format(self.api_client.ping()))
        print(u'')

    def command_deployment(self):
        print(u'{[ Command deployment ]}')

        from .system_command import SystemCommand
        from .commands import Commands
        self.system_command = SystemCommand(self.env)

        if not self.system_command:
            print(u'Failed to instantiate SystemCommand...')
            return

        if self.conf:
            sudo_bool = False
            if self.env.os.Windows:
                sudo_output, exit_status = self.system_command.execute(Commands.Windows.isUserAdmin)
                sudo_bool = sudo_output == Commands.Windows.isUserAdmin_Return
            if self.env.os.Linux:
                sudo_output, exit_status = self.system_command.execute(Commands.Linux.isUserAdmin)
                sudo_bool = sudo_output == Commands.Linux.isUserAdmin_Return
            if self.env.os.Mac:
                sudo_output, exit_status = self.system_command.execute(Commands.Linux.isUserAdmin)
                sudo_bool = sudo_output == Commands.Linux.isUserAdmin_Return
            print(u'Current user is admin/sudo? {0}'.format(sudo_bool))
        print(u'')

    ###########################################################################

    def get_current_username(self):
        username = str()
        if self.env.os.Linux:
            username = pwd.getpwuid(os.getuid()).pw_name
        return username

    @staticmethod
    def is_file(path):
        return os.path.isfile(path)

    @staticmethod
    def is_dir(path):
        return os.path.isdir(path)

    @staticmethod
    def is_readable(path):
        return os.access(path, os.R_OK)

    @staticmethod
    def is_writable(path):
        return os.access(path, os.W_OK)
