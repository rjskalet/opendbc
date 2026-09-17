"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from enum import StrEnum

from opendbc.car import Bus, structs
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.gm.values import CAR
from opendbc.can.parser import CANParser
from opendbc.sunnypilot.car.gm.values_ext import GMFlagsSP


class CarStateExt:
  def __init__(self, CP, CP_SP):
    self.CP = CP
    self.CP_SP = CP_SP

  def update(self, ret: structs.CarState, can_parsers: dict[StrEnum, CANParser]) -> None:
    pt_cp = can_parsers[Bus.pt]

    # Suburban lateral-v2 intentionally allows steering at standstill. The GM
    # base CarState sets lowSpeedAlert whenever vEgo dips below minSteerSpeed.
    # With minSteerSpeed == 0, normal estimator noise can make vEgo slightly
    # negative at a stop and produce the nonsensical "Below 0 mph" alert.
    # Suppress only that software edge case; EPS temporary/permanent faults are
    # still reported independently through steerFaultTemporary/Permanent.
    if self.CP.carFingerprint == CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN and self.CP.minSteerSpeed <= 0.0:
      ret.lowSpeedAlert = False

    if self.CP_SP.flags & GMFlagsSP.NON_ACC:
      ret.cruiseState.enabled = pt_cp.vl["ECMCruiseControl"]["CruiseActive"] != 0
      ret.cruiseState.speed = pt_cp.vl["ECMCruiseControl"]["CruiseSetSpeed"] * CV.KPH_TO_MS
      ret.accFaulted = False
