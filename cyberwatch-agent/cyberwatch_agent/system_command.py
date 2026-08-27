#!/usr/bin/env python3
# coding: utf-8

import codecs
import subprocess

UTF8_HEADER = "[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8;\n"

class SystemCommand(object):
    BASH_PATH = ['/bin/bash']
    POWERSHELL_PATH = ['PowerShell', '-NoProfile', '-NonInteractive', '-']

    def __init__(self, environs):
        self.env = environs

    def execute(self, command):
        if self.env.os.Linux:
            return self._shell_exec(self.BASH_PATH, command)
        if self.env.os.Windows:
            # Add two newline to ensure the end of the powershell script is executed
            # See https://gitlab.cbw.io/CyberwatchTeam/cyberwatch-agent/-/issues/88
            wrapped_command = UTF8_HEADER + command + "\n\n"
            encoded_command = self._powershell_encode_string(wrapped_command)
            return self._shell_exec(self.POWERSHELL_PATH, encoded_command)
        if self.env.os.Mac:
            return self._shell_exec(self.BASH_PATH, command)

    @staticmethod
    def _shell_exec(shell_path, command):
        shell = subprocess.Popen(shell_path,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 encoding='utf-8',
                                 errors='replace')

        try:
            # stop after timeout of 6 hours
            output = shell.communicate(command, timeout=21600)[0].strip()
        except subprocess.TimeoutExpired as exception:
            shell.kill()
            output = f"ERROR: timeout after {exception.timeout} seconds"

        output = output.replace(codecs.BOM_UTF8.decode(), "")
        return output, shell.returncode

    def _powershell_encode_string(self, string):
        """Use the '$([char]0x2121)' powershell syntax to encode non ascii
        characters."""
        return "".join(self._powershell_encode_char(char) for char in string)

    @staticmethod
    def _powershell_encode_char(char):
        unicode_code = ord(char)
        if unicode_code >= 128:
            return f"$([char]0x{unicode_code:x})"
        return char
