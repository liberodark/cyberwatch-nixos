#!/usr/bin/env python3
# coding: utf-8


class Commands(object):
    class Linux(object):
        isUserAdmin = (
            "sudo id -u"
        )

        isUserAdmin_Return = (
            "0"
        )

    class Windows(object):
        isUserAdmin = (
            "(New-Object Security.Principal.WindowsPrincipal"
            " ([Security.Principal.WindowsIdentity]::GetCurrent()))"
            ".IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)"
        )

        isUserAdmin_Return = (
            "True"
        )
