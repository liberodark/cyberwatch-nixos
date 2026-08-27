#!/usr/bin/env python3
# coding: utf-8

import os
import os.path
import platform
import sys
import time
import glob

from shutil import rmtree

from . import APP_NAME

LINUX_CONF_DIR = '/etc/{0}/'.format(APP_NAME)
LINUX_LOGS_DIR = '/var/log/{0}/'.format(APP_NAME)
MAC_CONF_DIR = '/etc/{0}/'.format(APP_NAME)
MAC_LOGS_DIR = '/var/log/{0}/'.format(APP_NAME)
WINDOWS_LOGS_DIR = 'logs'
CONF_FILE_NAME = 'agent.conf'
LOGS_FILE_NAME = 'agent.log'

###############################################################################


class LinuxPackageManager(object):
    APT = False
    RPM = False
    PACMAN = False

    def __init__(self):
        if os.path.exists('/etc/apt'):
            self.APT = True
        if os.path.exists('/etc/yum'):
            self.RPM = True
        if os.path.exists('/etc/pacman.conf'):
            self.PACMAN = True

    def __str__(self):
        if self.APT:
            return 'APT'
        elif self.RPM:
            return 'RPM'
        elif self.PACMAN:
            return 'PACMAN'
        else:
            return str()

###############################################################################


class OperatingSystem(object):
    Linux = False
    Windows = False
    Mac = False
    PackageManager = LinuxPackageManager()

    def __init__(self):
        if platform.system() == 'Linux':
            self.Linux = True

        if platform.system() == 'Windows':
            self.Windows = True

        if platform.system() == 'Darwin':
            self.Mac = True

    def is_supported(self):
        return self.Linux ^ self.Windows ^ self.Mac

    def __str__(self):
        return platform.system()

###############################################################################


class Environs(object):
    def __init__(self):
        self.os = OperatingSystem()

        if self.os.Linux:
            self.app_path = os.path.dirname(os.path.realpath(__file__))
            self.config_path = os.path.join(LINUX_CONF_DIR, CONF_FILE_NAME)
            self.logs_path = LINUX_LOGS_DIR
            self.logs_file = os.path.join(LINUX_LOGS_DIR, LOGS_FILE_NAME)

        if self.os.Mac:
            self.app_path = os.path.dirname(os.path.realpath(__file__))
            self.config_path = os.path.join(MAC_CONF_DIR, CONF_FILE_NAME)
            self.logs_path = MAC_LOGS_DIR
            self.logs_file = os.path.join(MAC_LOGS_DIR, LOGS_FILE_NAME)

        if self.os.Windows:
            if getattr(sys, 'frozen', False):
                self.app_path = os.path.dirname(sys.executable)
            else:
                self.app_path = os.path.dirname(os.path.dirname(__file__))
            self.config_path = os.path.join(self.app_path, CONF_FILE_NAME)
            self.logs_path = os.path.join(self.app_path, WINDOWS_LOGS_DIR)
            self.logs_file = os.path.join(self.logs_path, LOGS_FILE_NAME)


def deleteOldPyinstallerFolders(time_threshold=7200):
    """Deletes MEIPASS folders older that `time_treshold` (seconds)."""

    try:
        base_path = sys._MEIPASS
    except Exception:
        # Not run with PyInstaller OneFolder mode
        return

    tmp_path = os.path.abspath(os.path.join(base_path, '..')) # Go to parent folder of MEIPASS

    mei_folders = glob.glob(os.path.join(tmp_path, '_MEI*'))
    for item in mei_folders:
        if (time.time()-os.path.getctime(item)) > time_threshold:
            rmtree(item)
