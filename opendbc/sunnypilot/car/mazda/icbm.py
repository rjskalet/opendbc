"""Mazda Intelligent Cruise Button Management interface."""

from opendbc.car import structs, DT_CTRL
from opendbc.car.can_definitions import CanData
from opendbc.car.mazda import mazdacan
from opendbc.car.mazda.values import Buttons
from opendbc.sunnypilot.car.icbm_actuation_profile import get_actuation_profile
from opendbc.sunnypilot.car.intelligent_cruise_button_management_interface_base import IntelligentCruiseButtonManagementInterfaceBase

SendButtonState = structs.IntelligentCruiseButtonManagement.SendButtonState

BUTTONS = {
  SendButtonState.increase: Buttons.SET_PLUS,
  SendButtonState.decrease: Buttons.SET_MINUS,
}


class IntelligentCruiseButtonManagementInterface(IntelligentCruiseButtonManagementInterfaceBase):
  def __init__(self, CP, CP_SP):
    super().__init__(CP, CP_SP)
    self.tap_period = 1. / get_actuation_profile(CP.brand).tap_rate_hz

  def update(self, CC_SP, CS, packer, frame, last_button_frame) -> list[CanData]:
    can_sends = []
    self.CC_SP = CC_SP
    self.ICBM = CC_SP.intelligentCruiseButtonManagement
    self.frame = frame
    self.last_button_frame = last_button_frame

    # Never forge a set-speed frame over the driver's physical SET+/SET- input.
    if CS.accel_button or CS.decel_button:
      return can_sends

    if self.ICBM.sendButton != SendButtonState.none:
      if (self.frame - self.last_button_frame) * DT_CTRL > self.tap_period:
        self.button_frame += 1
        button_counter_offset = [1, 1, 0, None][self.button_frame % 4]
        if button_counter_offset is not None:
          can_sends.append(mazdacan.create_button_cmd(
            packer, self.CP, CS.crz_btns_counter + button_counter_offset, BUTTONS[self.ICBM.sendButton]))
          self.last_button_frame = self.frame

    return can_sends
