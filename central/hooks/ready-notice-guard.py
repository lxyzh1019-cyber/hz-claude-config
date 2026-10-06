#!/usr/bin/env python3
"""Retired in v3.1.31. It sent a finished answer back when no notice had been sent, and the answer then showed twice.
The notice now comes before the answer: notice-reminder.py (PostToolUse) asks for it right after a pull request opens
or is marked ready. This file stays so that no file has to be deleted from the repository."""
import sys
sys.exit(0)
