"""Constants for the Remote Buttons integration."""

DOMAIN = "remote_buttons"

# Delay (seconds) after a learn_command service call before re-scanning storage.
LEARN_SCAN_DELAY = 30

# Delay (seconds) after a delete_command service call before re-scanning storage.
# Must exceed the underlying integration's storage write delay (e.g. Broadlink uses 15 s).
DELETE_SCAN_DELAY = 30

# Default values for IR command parameters.
DEFAULT_IR_DELAY = 0.5
DEFAULT_IR_REPEATS = 1
