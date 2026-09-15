"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
# ruff: noqa: E501

from opendbc.car.gm.values import CAR


# The 2019 Suburban camera-harness configuration shares the observed powertrain
# CAN map with the 2019 Yukon. Live VIN + camera-bus checks in car_helpers.py
# disambiguate the Suburban before interface selection.
FINGERPRINTS_EXT = {
  CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN: [{
    190: 6, 193: 8, 197: 8, 201: 8, 208: 8, 209: 7, 211: 2, 241: 6, 249: 8, 288: 5, 289: 8, 298: 8, 304: 1, 309: 8, 311: 8, 313: 8, 320: 3, 328: 1, 352: 5, 381: 8, 384: 4, 386: 8, 388: 8, 413: 8, 451: 8, 452: 8, 453: 6, 455: 7, 460: 5, 463: 3, 479: 3, 481: 7, 485: 8, 489: 8, 497: 8, 500: 6, 501: 8, 510: 8, 528: 5, 532: 6, 534: 2, 562: 8, 563: 5, 587: 8, 608: 8, 609: 6, 610: 6, 611: 6, 612: 8, 613: 8, 707: 8, 761: 7, 800: 6, 801: 8, 810: 8, 840: 5, 842: 5, 844: 8, 848: 4, 977: 8, 1001: 8, 1017: 8, 1020: 8, 1217: 8, 1221: 5, 1233: 8, 1249: 8, 1265: 8, 1267: 1, 1280: 4, 1300: 8, 1355: 8, 1611: 8
  }],
}
