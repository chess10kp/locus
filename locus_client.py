#!/usr/bin/env python3
# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: basic
# ruff: ignore

import socket
import sys

SOCKET_PATH = "/tmp/locus_socket"


def send_message(message: str):
    """Send a message to locus via Unix socket"""
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(SOCKET_PATH)
        client.send(message.encode("utf-8"))
        client.close()
    except Exception as e:
        print(f"Failed to send message: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "launcher":
        if len(sys.argv) > 2:
            app_name = " ".join(sys.argv[2:])
            send_message(f"launcher {app_name}")
        else:
            send_message("launcher")
    elif len(sys.argv) >= 2:
        message = " ".join(sys.argv[1:])
        send_message(message)
    else:
        print(
            "Usage: python locus_client.py launcher [app] | <message>", file=sys.stderr
        )
        sys.exit(1)
