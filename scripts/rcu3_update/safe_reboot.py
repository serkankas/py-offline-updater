#!/usr/bin/env python3
"""Safe reboot - sync filesystems, wait, then reboot cleanly."""

import os
import time
import subprocess

os.sync()
time.sleep(2)
subprocess.run(['systemctl', 'reboot'])
