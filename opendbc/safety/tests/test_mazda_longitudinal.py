#!/usr/bin/env python3
import unittest

from opendbc.car.mazda.values import MazdaSafetyFlags
from opendbc.car.structs import CarParams
from opendbc.safety.tests.libsafety import libsafety_py
import opendbc.safety.tests.common as common
from opendbc.safety.tests.common import CANPackerSafety


class TestMazdaLongitudinalSafety(unittest.TestCase):
  SAFETY_PARAM = MazdaSafetyFlags.LONG | MazdaSafetyFlags.STEER_TO_ZERO_EPS

  def setUp(self):
    self.packer = CANPackerSafety("mazda_2017")
    self.safety = libsafety_py.libsafety
    self.safety.set_safety_hooks(CarParams.SafetyModel.mazda, self.SAFETY_PARAM)
    self.safety.init_tests()

  def _tx(self, msg):
    return self.safety.safety_tx_hook(msg)

  def _rx(self, msg):
    return self.safety.safety_rx_hook(msg)

  def _button_msg(self, resume=False, cancel=False, set_m=False, set_p=False):
    values = {
      "CAN_OFF": cancel,
      "CAN_OFF_INV": (cancel + 1) % 2,
      "RES": resume,
      "RES_INV": (resume + 1) % 2,
      "SET_M": set_m,
      "SET_M_INV": (set_m + 1) % 2,
      "SET_P": set_p,
      "SET_P_INV": (set_p + 1) % 2,
    }
    return self.packer.make_can_msg_safety("CRZ_BTNS", 0, values)

  def _pedals(self, active=False, armed=False):
    return self.packer.make_can_msg_safety("PEDALS", 0, {"ACC_ACTIVE": active, "ACC_OFF": armed})

  def _accel(self, accel, bus=0, active=False):
    return self.packer.make_can_msg_safety("CRZ_INFO", bus, {"ACCEL_CMD": accel, "ACC_ACTIVE": active})

  def _crz_ctrl(self, active, bus=0):
    return self.packer.make_can_msg_safety("CRZ_CTRL", bus, {"CRZ_ACTIVE": active})

  def test_engagement_requires_recent_driver_button(self):
    for _ in range(3):
      self._rx(self._pedals(active=True))
      self.assertFalse(self.safety.get_controls_allowed())

    self._rx(self._pedals(active=False, armed=True))
    self._rx(self._button_msg(set_m=True))
    self._rx(self._pedals(active=True))
    self.assertTrue(self.safety.get_controls_allowed())

  def test_cancel_exits_controls(self):
    self._rx(self._button_msg(set_p=True))
    self._rx(self._pedals(active=True))
    self.assertTrue(self.safety.get_controls_allowed())

    self._rx(self._button_msg(cancel=True))
    self.assertFalse(self.safety.get_controls_allowed())

  def test_accel_limits_apply_on_car_and_camera_buses(self):
    for bus in (0, 2):
      for controls_allowed in (False, True):
        self.safety.set_controls_allowed(controls_allowed)
        for accel in (-3.501, -3.5, 0.0, 2.0, 2.001):
          expected = accel == 0.0 or (controls_allowed and -3.5 <= accel <= 2.0)
          self.assertEqual(expected, self._tx(self._accel(accel, bus=bus)), (bus, controls_allowed, accel))

  def test_engaged_bits_are_gated_on_controls(self):
    for bus in (0, 2):
      self.safety.set_controls_allowed(False)
      self.assertTrue(self._tx(self._accel(0.0, bus=bus, active=False)))
      self.assertFalse(self._tx(self._accel(0.0, bus=bus, active=True)))
      self.assertTrue(self._tx(self._crz_ctrl(False, bus=bus)))
      self.assertFalse(self._tx(self._crz_ctrl(True, bus=bus)))

      self.safety.set_controls_allowed(True)
      self.assertTrue(self._tx(self._accel(0.0, bus=bus, active=True)))
      self.assertTrue(self._tx(self._crz_ctrl(True, bus=bus)))

  def test_stock_standby_crz_info_is_allowed(self):
    def pegged(d4, d5, counter):
      dat = bytes([0x01, 0xff, 0xe3, 0xff, d4, d5, counter])
      return dat + bytes([(0xff - sum(dat)) & 0xff])

    for bus in (0, 2):
      for controls_allowed in (False, True):
        self.safety.set_controls_allowed(controls_allowed)
        for d4, d5 in ((0xc0, 0x00), (0xc0, 0x80), (0xc4, 0x80)):
          self.assertTrue(self._tx(common.make_msg(bus, 0x21b, 8, pegged(d4, d5, 0))))

  def test_synthetic_radar_templates_allowed(self):
    radar = {
      0x499: bytes.fromhex("0008c00000000000"),
      0x361: bytes.fromhex("fff7fefe1fc00080"),
      0x362: bytes.fromhex("fff7fefe1fc78c80"),
      0x363: bytes.fromhex("fff7fefe1fc00000"),
      0x364: bytes.fromhex("fff7fefe1fc00000"),
      0x365: bytes.fromhex("fff7fe7ffbff3fc0"),
      0x366: bytes.fromhex("fff7fe7ffbff3fc0"),
    }
    for bus in (0, 2):
      for controls_allowed in (False, True):
        self.safety.set_controls_allowed(controls_allowed)
        for addr, dat in radar.items():
          self.assertTrue(self._tx(common.make_msg(bus, addr, 8, dat)))

  def test_radar_uds_allowlist_is_narrow(self):
    self.assertTrue(self._tx(common.make_msg(0, 0x764, 8, bytes.fromhex("023e800000000000"))))
    self.assertTrue(self._tx(common.make_msg(0, 0x764, 8, bytes.fromhex("0210020000000000"))))
    self.assertTrue(self._tx(common.make_msg(0, 0x764, 8, bytes.fromhex("0210010000000000"))))
    self.assertFalse(self._tx(common.make_msg(0, 0x764, 8, bytes.fromhex("0210030000000000"))))
    self.assertFalse(self._tx(common.make_msg(0, 0x764, 8, bytes.fromhex("0227010000000000"))))
    self.assertFalse(self._tx(common.make_msg(2, 0x764, 8, bytes.fromhex("023e800000000000"))))


if __name__ == "__main__":
  unittest.main()
