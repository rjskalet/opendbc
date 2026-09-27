import unittest
from types import SimpleNamespace
from unittest.mock import patch

from opendbc.can import CANPacker, CANParser
from opendbc.car import Bus, structs
from opendbc.car.car_helpers import interfaces
from opendbc.car.mazda import mazdacan
from opendbc.car.mazda.carstate import CarState
from opendbc.car.mazda.values import CAR, Buttons, MazdaFlags
from opendbc.sunnypilot.car.mazda.icbm import IntelligentCruiseButtonManagementInterface

SendButtonState = structs.IntelligentCruiseButtonManagement.SendButtonState


class TestMazdaCruiseButtons(unittest.TestCase):
  def setUp(self):
    self.packer = CANPacker("mazda_2017")
    self.parser = CANParser("mazda_2017", [("CRZ_BTNS", 0)], 0)
    self.CP = structs.CarParams(brand="mazda", flags=int(MazdaFlags.GEN1))

  def assert_button_signal(self, button, signal):
    msg = mazdacan.create_button_cmd(self.packer, self.CP, 0, button)
    self.parser.update([0, [msg]])
    self.assertEqual(self.parser.vl["CRZ_BTNS"][signal], 1)

  def test_button_signal_mapping(self):
    self.assert_button_signal(Buttons.SET_PLUS, "SET_P")
    self.assert_button_signal(Buttons.RESUME, "RES")
    self.assert_button_signal(Buttons.SET_MINUS, "SET_M")

  def test_received_button_interpretation(self):
    CP = interfaces[CAR.MAZDA_CX9].get_non_essential_params(CAR.MAZDA_CX9)
    CP_SP = interfaces[CAR.MAZDA_CX9].get_non_essential_params_sp(CP, CAR.MAZDA_CX9)

    for button, accel_pressed, decel_pressed in (
      (Buttons.SET_PLUS, 1, 0),
      (Buttons.RESUME, 0, 0),
      (Buttons.SET_MINUS, 0, 1),
    ):
      with self.subTest(button=button):
        car_state = CarState(CP, CP_SP)
        parsers = car_state.get_can_parsers(CP, CP_SP)
        car_state.update(parsers)
        msg = mazdacan.create_button_cmd(self.packer, CP, 0, button)
        parsers[Bus.pt].update([1, [msg]])

        car_state.update(parsers)
        self.assertEqual(car_state.accel_button, accel_pressed)
        self.assertEqual(car_state.decel_button, decel_pressed)

  def test_icbm_suppressed_while_driver_holds_set_button(self):
    interface = IntelligentCruiseButtonManagementInterface(self.CP, structs.CarParamsSP())
    CC_SP = structs.CarControlSP()
    CC_SP.intelligentCruiseButtonManagement.sendButton = SendButtonState.increase

    for accel_button, decel_button in ((1, 0), (0, 1)):
      CS = SimpleNamespace(accel_button=accel_button, decel_button=decel_button, crz_btns_counter=0)
      with patch("opendbc.sunnypilot.car.mazda.icbm.mazdacan.create_button_cmd") as create_button_cmd:
        self.assertEqual(interface.update(CC_SP, CS, self.packer, 100, 0), [])
        create_button_cmd.assert_not_called()


if __name__ == "__main__":
  unittest.main()
