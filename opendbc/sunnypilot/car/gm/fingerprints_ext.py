"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
# ruff: noqa: E501

# Keep this extension table empty for the ACC camera-harness Suburban. Its
# observed legacy CAN fingerprint is identical to the GMC Yukon, so adding a
# duplicate candidate here would make legacy fingerprinting ambiguous. The
# shared Yukon fingerprint is instead disambiguated in car_helpers.py using VIN
# and camera-bus diagnostics.
FINGERPRINTS_EXT = {}
