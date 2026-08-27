#!/usr/bin/env python3
# coding: utf-8

from cyberwatch_agent.checks import Checks

import configparser

class ApiConfig(object):
    base_url = ''
    access_key_id = ''
    secret_access_key = ''
    allow_selfsigned = False
    registration_key_id = ''
    secret_registration_key = ''
    groups = ''
    category = ''


class ProxyConfig(object):
    enabled = False
    hosts = {'http': '', 'https': ''}


class WsusProxyConfig(object):
    enabled = False
    host = ''


class Configuration(object):
    def __init__(self, environs):
        self.env = environs
        self.api = ApiConfig()
        self.proxy = ProxyConfig()
        self.wsus_proxy = WsusProxyConfig()

    def load(self):
        parser = configparser.ConfigParser()

        try:
            with open(self.env.config_path) as f:
                parser.read_file(f)
        except FileNotFoundError:
            print(f"Error when reading '{self.env.config_path}'. File not found.")
            return self
        except PermissionError:
            print(f"Error when reading '{self.env.config_path}'. Permission Denied. Try with 'sudo'")
            return self
        except Exception as e:
            print(e)
            print(f"Error when reading '{self.env.config_path}'.")
            return self

        if parser.has_section('api'):
            if parser.has_option('api', 'base_url'):
                self.api.base_url = parser.get('api', 'base_url')
            if parser.has_option('api', 'access_key_id'):
                self.api.access_key_id = parser.get('api', 'access_key_id')
            if parser.has_option('api', 'secret_access_key'):
                self.api.secret_access_key = parser.get('api', 'secret_access_key')
            if parser.has_option('api', 'registration_key_id'):
                self.api.registration_key_id = parser.get('api', 'registration_key_id')
            if parser.has_option('api', 'secret_registration_key'):
                self.api.secret_registration_key = parser.get('api', 'secret_registration_key')
            if parser.has_option('api', 'groups'):
                self.api.groups = parser.get('api', 'groups')
            if parser.has_option('api', 'category'):
                self.api.category = parser.get('api', 'category')
            if parser.has_option('api', 'allow_selfsigned'):
                try:
                    self.api.allow_selfsigned = parser.getboolean('api', 'allow_selfsigned')
                except ValueError:
                    print('Configuration: api.allow_selfsigned: is not a boolean.')

        if parser.has_section('proxy'):
            if parser.has_option('proxy', 'enabled'):
                try:
                    self.proxy.enabled = parser.getboolean('proxy', 'enabled')
                except ValueError:
                    print('Configuration: proxy.enabled: is not a boolean.')
                if self.proxy.enabled:
                    if parser.has_option('proxy', 'host'):
                        self.proxy.hosts = {
                            'http': parser.get('proxy', 'host'),
                            'https': parser.get('proxy', 'host')}

        if parser.has_section('wsus_proxy'):
            if parser.has_option('wsus_proxy', 'enabled'):
                try:
                    self.wsus_proxy.enabled = parser.getboolean('wsus_proxy', 'enabled')
                except ValueError:
                    print('Configuration: wsus_proxy.enabled: is not a boolean.')
                if self.wsus_proxy.enabled:
                    if parser.has_option('wsus_proxy', 'host'):
                        self.wsus_proxy.host = parser.get('wsus_proxy', 'host')
        return self

    def is_valid(self):
        return self.api.base_url and (not self.api.base_url.isspace())

    def is_registered(self):
        return self.api.access_key_id and \
               len(self.api.access_key_id.strip()) >= 32 and \
               self.api.secret_access_key and \
               len(self.api.secret_access_key.strip()) >= 32

    def has_registration_credentials(self):
        return self.api.registration_key_id and self.api.secret_registration_key

    def save(self):
        if not Checks.is_writable(self.env.config_path):
            print(u'Config file is not writable!')
            return False

        new_conf = configparser.ConfigParser()
        new_conf.add_section('api')
        new_conf.set('api', 'base_url', self.api.base_url)
        new_conf.set('api', 'access_key_id', self.api.access_key_id)
        new_conf.set('api', 'secret_access_key', self.api.secret_access_key)
        new_conf.set('api', 'registration_key_id', self.api.registration_key_id)
        new_conf.set('api', 'secret_registration_key', self.api.secret_registration_key)
        new_conf.set('api', 'groups', self.api.groups)
        new_conf.set('api', 'category', self.api.category)
        new_conf.set('api', 'allow_selfsigned', str(self.api.allow_selfsigned))
        new_conf.add_section('proxy')
        new_conf.set('proxy', 'enabled', str(self.proxy.enabled))
        new_conf.set('proxy', 'host', self.proxy.hosts.get('http'))
        if self.env.os.Windows:
            new_conf.add_section('wsus_proxy')
            new_conf.set('wsus_proxy', 'enabled', str(self.wsus_proxy.enabled))
            new_conf.set('wsus_proxy', 'host', self.wsus_proxy.host)

        try:
            with open(self.env.config_path, 'w') as file_:
                new_conf.write(file_)
                print(u'Configuration file updated successfully!')
        except Exception as e:
            print(u'Failed to save configuration file: {0}'.format(e))
