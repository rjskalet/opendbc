"""Mazda-specific sunnypilot car-state extensions."""

from enum import StrEnum

from opendbc.car import Bus, structs
from opendbc.can.parser import CANParser
from opendbc.car.common.conversions import Conversions as CV


class CarStateExt:
  def __init__(self, CP, CP_SP):
    self.CP = CP
    self.CP_SP = CP_SP

  def update(self, ret: structs.CarState, ret_sp: structs.CarStateSP, can_parsers: dict[StrEnum, CANParser]) -> None:
    cp_cam = can_parsers[Bus.cam]

    # The current SunnyPilot Mazda DBC exposes the camera's speed-sign value and its display
    # bit. On this US-market CX-9 that display path is mph. Keep a strict plausibility bound;
    # invalid/sentinel values become no limit rather than a bad speed-limit command.
    # ZoomPilot additionally names the adjacent two-bit unit field; that DBC-only cleanup can
    # be folded in independently without changing this branch's control behavior.
    sign = cp_cam.vl["CAM_TRAFFIC_SIGNS"]
    speed_sign = sign["SPEED_SIGN"]
    if sign["SPEED_SIGN_ON"] == 1 and 0 < speed_sign <= 90:
      ret_sp.speedLimit = float(speed_sign) * CV.MPH_TO_MS
    else:
      ret_sp.speedLimit = 0.0
