#!/usr/bin/env python3
# coding: utf-8

import sys
import argparse
import time

from cyberwatch_agent import APP_NAME, APP_VERSION
from cyberwatch_agent.system_info import Environs, deleteOldPyinstallerFolders
from cyberwatch_agent.configuration import Configuration
from cyberwatch_agent.logger import Logger
from cyberwatch_agent.api_client import ApiClient
from cyberwatch_agent.system_command import SystemCommand
from cyberwatch_agent.checks import Checks


class Agent(object):
    """ CyberWatch SAS Agent """

    def __init__(self):
        """ Instantiate the Agent """

        self.env = Environs()
        self.args = None
        self.log = None
        self.config = None
        self.api_client = None
        self.start_time = time.time()

    def _parse_args(self, args):
        """ Parse command line arguments """

        parser = argparse.ArgumentParser()
        parser.add_argument('-V', '--version',
                            action='version', version=APP_VERSION)
        parser.add_argument('-q', '--quiet', action='store_true',
                            help='quiet output: print only errors')
        parser.add_argument('-d', '--debug', action='store_true',
                            help='debug output')
        parser.add_argument('--api-url', metavar='URL',
                            help='set api base url when registering')
        parser.add_argument('--access-key-id', metavar='KEY',
                            help='set api access key id when registering')
        parser.add_argument('--secret-access-key', metavar='KEY',
                            help='set api secret access key when registering')
        parser.add_argument('--category', metavar='CATEGORY', default='server',
                            help='set the category of the computer when registering')
        parser.add_argument('--later', action="store_true",
                            help='Register only the next time the agent starts')
        parser.add_argument('--allow_selfsigned', metavar='bool',
                            help='allow selfsigned certificates from the Cyberwatch server (default false)')
        parser.add_argument('--proxy_enabled', metavar='bool',
                            help='enable proxy for Cyberwatch API requests (default false)')
        parser.add_argument('--proxy_host', metavar='URL',
                            help='set the proxy for Cyberwatch API requests '
                                 '(https://username:password@host:port/ format)')
        parser.add_argument('--groups', default=",", metavar='GROUPS',
                            help='set the server\'s groups by separating each one with a coma')

        if self.env.os.Windows:
            parser.add_argument('--wsus_proxy_enabled', metavar='bool',
                                help='enable proxy for Windows Update requests (default false)')
            parser.add_argument('--wsus_proxy_host', metavar='URL',
                                help='set the proxy for Windows Update requests '
                                     '(https://username:password@host:port/ format)')
        parser.add_argument('action', nargs='?', default='get_tasks',
                            choices=['check', 'register', 'get_tasks', 'set_config'])
        parser.add_argument('check', nargs='?', default='all', help=argparse.SUPPRESS,
                            choices=['all', 'env', 'conf', 'logging', 'api', 'deploy'])

        self.args = parser.parse_args(args)

    def start(self):
        """ Initialize the Agent """

        # If used in Unit Tests, self.args are defined in the Unit Tests e.g. Agent()._parse_args(['set_config'])
        # If used in production, self.args are passed with sys.argv
        if self.args is None:
            self._parse_args(sys.argv[1:])

        # Checks everything if needed
        if self.args.action == 'check':
            return Checks(self.env).check(self.args.check)

        # Check OS
        if not self.env.os.is_supported():
            return self.exit_failure(u'Operating System is not supported.')

        # Init logger
        self.log = Logger(self.env, self.args.debug, self.args.quiet).root_logger
        if not self.log:
            return self.exit_failure(u'Logger creation failed.')

        # Load configuration
        self.config = Configuration(self.env).load()
        if not self.config.is_valid():
            return self.exit_failure(u'An error occurs when reading config file: "{0}"'.format(self.env.config_path))

        # Run main
        self._main()

    def _main(self):
        """ Dispatch """

        # Print banner
        self.log.info(u'Starting {0} {1}'.format(APP_NAME, APP_VERSION))

        if self.args.action == 'register':
            if self.config.is_registered():
                self.log.info(u'{0} is already registered.'.format(APP_NAME))
                return
            self._save_config()
            if not self.args.later:
                self._register_from_saved_credentials()
                self._get_tasks()
        elif self.args.action == 'get_tasks':
            if not self.config.is_registered():
                self._try_to_register()
            self._get_tasks()
        elif self.args.action == 'set_config':
            self._set_config()

        run_time = round(time.time() - self.start_time, 2)

        self.log.info(u'{0} {1} done in {2}s'.format(APP_NAME, APP_VERSION, run_time))

        self._cleanup()

    ###########################################################################

    def _try_to_register(self):
        if self.config.has_registration_credentials():
            self._register_from_saved_credentials()
        else:
            return self.exit_failure(
                u'Agent does not seems to be registered.\nPlease run `{0} register`'.format(APP_NAME))

    def _save_config(self):
        self.config.api.registration_key_id = self.args.access_key_id
        self.config.api.secret_registration_key = self.args.secret_access_key
        self.config.api.base_url = self.args.api_url
        self.config.api.groups = self.args.groups
        self.config.api.category = self.args.category

        # Ensure all required information is provided
        self._assert_exists(self.config.api.registration_key_id, "access-key-id")
        self._assert_exists(self.config.api.secret_registration_key, "secret-access-key")
        self._assert_exists(self.config.api.base_url, "api-url")

        self._set_config()

    def _register_from_saved_credentials(self):
        self.log.info(u'Registering...')

        register_payload = {'os_type': str(self.env.os),
                            'package_manager': str(self.env.os.PackageManager),
                            'category': self.config.api.category,
                            'groups': self.config.api.groups}

        # Ensure all required information is provided
        self._assert_exists(self.config.api.registration_key_id, "access-key-id")
        self._assert_exists(self.config.api.secret_registration_key, "secret-access-key")
        self._assert_exists(self.config.api.base_url, "api-url")

        api_client = ApiClient(
            self.config,
            self.log,
            key_id=self.config.api.registration_key_id,
            secret_key=self.config.api.secret_registration_key
        )

        new_server = api_client.create_server(register_payload)

        if new_server:
            self._save_server_information(new_server)
        else:
            self.log.error(u'Failed to register agent.')
            sys.exit(1)

    def _assert_exists(self, config_field, name):
        if config_field is None:
            self.log.error(u'No value has been specified for \'{}\''.format(name))
            self.exit_failure()


    def _cleanup(self):
        if self.env.os.Windows:
            deleteOldPyinstallerFolders()


    def _save_server_information(self, server):
        try:
            self.log.info(u'Saving configuration to file: {0}'.format(self.env.config_path))

            self.config.api.access_key_id = server.get('access_key_id')
            self.config.api.secret_access_key = server.get('secret_access_key')

            # Delete registration credentials
            self.config.api.registration_key_id = ""
            self.config.api.secret_registration_key = ""

            self.config.save()
        except Exception as e:
            self.log.error(u'Failed to save configuration file.')
            self.log.error(str(e))

    ###########################################################################

    def _get_tasks(self):
        prev_script_to_execute_id = -1

        # Init API Client
        self.api_client = ApiClient(self.config, self.log)

        while True:
            self.log.info(u'Fetching tasks...')

            # Fetch tasks
            tasks = self.api_client.get_tasks()

            if not tasks:
                self.log.error(u'Failed to fetch tasks!')
                return

            self.log.debug(u'[TASKS>>\n{0}\n<<TASKS]'.format(tasks))

            # Check if script is pending
            script_to_execute_id = tasks.get('script_to_execute')
            if script_to_execute_id:
                if prev_script_to_execute_id == script_to_execute_id:
                    self.log.info(u'Duplicate script execution. No script to execute.')
                    break
                prev_script_to_execute_id = script_to_execute_id

                self.log.info(u'Executing script...')
                self._execute_script(script_to_execute_id)
            else:
                self.log.info(u'No script to execute.')
                break

    ###########################################################################

    def _set_config(self):
        # Check if something need to be changed
        config_file_should_change = any([
            self.args.api_url,
            self.args.allow_selfsigned,
            self.args.proxy_enabled,
            self.args.proxy_host,
            self.env.os.Windows and self.args.wsus_proxy_enabled,
            self.env.os.Windows and self.args.wsus_proxy_host
        ])
        if config_file_should_change:
            self.log.info(u'Updating config file...')
        else:
            return

        # Get config vars from args
        # - Api section
        if self.args.api_url:
            self.config.api.base_url = self.args.api_url
        if self.args.allow_selfsigned:
            self.config.api.allow_selfsigned = self._check_param_is_bool(self.args.allow_selfsigned)
        # - Proxy section
        if self.args.proxy_enabled:
            self.config.proxy.enabled = self._check_param_is_bool(self.args.proxy_enabled)
        if self.args.proxy_host:
            self.config.proxy.hosts = {
                'http': self.args.proxy_host,
                'https': self.args.proxy_host}
        # - WSUS_Proxy section
        if self.env.os.Windows:
            if self.args.wsus_proxy_enabled:
                self.config.wsus_proxy.enabled = self._check_param_is_bool(self.args.wsus_proxy_enabled)
            if self.args.wsus_proxy_host:
                self.config.wsus_proxy.host = self.args.wsus_proxy_host

        # Update config file
        try:
            self.config.save()
            # Reload
            self.config = Configuration(self.env).load()
            self.api_client = ApiClient(self.config, self.log)
        except Exception as e:
            self.log.error(u'Failed to save configuration file.')
            self.log.error(str(e))

    ###########################################################################

    def _check_param_is_bool(self, s):
        if s.lower() == 'true':
            return True
        elif s.lower() == 'false':
            return False
        else:
            self.log.error(u'{} should be a boolean.'.format(s))
            self.exit_failure()

    ###########################################################################

    def _execute_script(self, id_):

        # Fetch script
        self.log.info(u'Downloading script {0}...'.format(id_))
        script = self.api_client.get_script(id_)

        if not script:
            self.log.error(u'Failed to download script!')
            return

        self.log.debug(u'[SCRIPT_CONTENT>>\n{0}\n<<SCRIPT_CONTENT]'.format(script['contents']))

        # Execute script
        self.log.info(u'Executing script...')
        output, exit_status = SystemCommand(self.env).execute(script['contents'])

        self.log.debug(u'[SCRIPT_OUTPUT>>\n{0}\n<<SCRIPT_OUTPUT]'.format(output))

        # Upload script output
        self.log.info(u'Uploading script output...')
        upload = self.api_client.update_script(id_, {'output': output, 'exit_status': exit_status})

        if upload:
            self.log.info(u'Script output uploaded successfully.')
        else:
            self.log.error(u'Failed to upload script output!')

    ###########################################################################

    @staticmethod
    def exit_failure(message=u''):
        print(u'{0}\nQUITTING!'.format(message))
        sys.exit(1 ** 1)
