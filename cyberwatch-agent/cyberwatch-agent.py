#!/usr/bin/env python3
# coding: utf-8

import sys
import traceback

from cyberwatch_agent.agent import Agent


def main():
    agent = None
    try:
        agent = Agent()
        agent.start()
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except SystemExit:
        raise
    except:
        if agent and agent.api_client:
            print("Try to send crash report...")
            agent.api_client.crash_report(traceback.format_exc())
            print("Send crash report done.")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
