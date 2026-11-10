import unittest
from types import SimpleNamespace

from opendbc.can import CANPacker
from opendbc.car import Bus, structs
from opendbc.car.car_helpers import interfaces
from opendbc.car.gm.fingerprints import FINGERPRINTS
from opendbc.car.gm import gmcan
from opendbc.car.gm.carcontroller import CarController
from opendbc.car.gm.carstate import REJECTED_LOOPBACK, CarState
from opendbc.car.gm.values import CAMERA_ACC_CAR, CAR, GM_RX_OFFSET, CanBus
from opendbc.testing import parameterized

CAMERA_DIAGNOSTIC_ADDRESS = 0x24b


class TestGMFingerprint(unittest.TestCase):
  @parameterized("car_model, fingerprints", FINGERPRINTS.items())
  def test_can_fingerprints(self, car_model, fingerprints):
    assert len(fingerprints) > 0

    assert all(len(finger) for finger in fingerprints)

    # The camera can sometimes be communicating on startup
    if car_model in CAMERA_ACC_CAR:
      for finger in fingerprints:
        for required_addr in (CAMERA_DIAGNOSTIC_ADDRESS, CAMERA_DIAGNOSTIC_ADDRESS + GM_RX_OFFSET):
          assert finger.get(required_addr) == 8, required_addr


class TestGMSuburbanSteeringLoopback(unittest.TestCase):
  def setUp(self):
    self.CP = interfaces[CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN].get_non_essential_params(CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN)
    self.CP_SP = interfaces[CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN].get_non_essential_params_sp(
      self.CP, CAR.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN,
    )
    self.packer = CANPacker("gm_global_a_powertrain_generated")

  def steering_msg(self, torque, counter=0, bus=CanBus.POWERTRAIN):
    msg = gmcan.create_steering_control(self.packer, CanBus.POWERTRAIN, torque, counter, True)
    return msg[0], msg[1], bus

  @staticmethod
  def update_parsers(parsers, nanos, messages):
    for parser in parsers.values():
      parser.update([nanos, messages])

  def test_rejected_loopback_counts_only_nonzero_torque_per_cycle(self):
    car_state = CarState(self.CP, self.CP_SP)
    parsers = car_state.get_can_parsers(self.CP, self.CP_SP)

    rejected = [
      self.steering_msg(10, counter=0, bus=CanBus.DROPPED),
      self.steering_msg(-10, counter=1, bus=CanBus.DROPPED),
      self.steering_msg(0, counter=2, bus=CanBus.DROPPED),
    ]
    self.update_parsers(parsers, 1, rejected)
    car_state.update(parsers)
    self.assertEqual(car_state.lkas_rejected, 2)

    for bus in (CanBus.LOOPBACK, CanBus.POWERTRAIN, CanBus.CAMERA):
      self.update_parsers(parsers, 2, [self.steering_msg(10, bus=bus)])
      car_state.update(parsers)
      self.assertEqual(car_state.lkas_rejected, 0)

    self.update_parsers(parsers, 3, [])
    car_state.update(parsers)
    self.assertEqual(car_state.lkas_rejected, 0)

  def test_rejected_loopback_does_not_affect_validity(self):
    rejected = CarState.get_can_parsers(self.CP, self.CP_SP)[REJECTED_LOOPBACK]
    self.assertTrue(rejected.can_valid)
    rejected.update([10_000_000_000, []])
    self.assertFalse(rejected.bus_timeout)
    self.assertTrue(rejected.can_valid)

  def test_accepted_loopback_counter_and_timestamp_are_unchanged(self):
    car_state = CarState(self.CP, self.CP_SP)
    parsers = car_state.get_can_parsers(self.CP, self.CP_SP)
    self.update_parsers(parsers, 20_000_000, [self.steering_msg(10, counter=2, bus=CanBus.LOOPBACK)])
    car_state.update(parsers)
    self.assertTrue(car_state.loopback_lka_steering_cmd_updated)
    self.assertEqual(car_state.loopback_lka_steering_cmd_ts_nanos, 20_000_000)
    self.assertEqual(parsers[Bus.loopback].vl["ASCMLKASteeringCmd"]["RollingCounter"], 2)
    self.assertEqual(car_state.lkas_rejected, 0)

    self.update_parsers(parsers, 21_000_000, [])
    car_state.update(parsers)
    self.assertFalse(car_state.loopback_lka_steering_cmd_updated)
    self.assertEqual(car_state.loopback_lka_steering_cmd_ts_nanos, 20_000_000)

  def test_controller_preserves_spacing_and_counter_synchronization(self):
    controller = CarController({}, self.CP, self.CP_SP)
    CC = structs.CarControl(latActive=True)
    CC.actuators.torque = 1.0
    CS = SimpleNamespace(
      out=SimpleNamespace(steeringTorque=0.0),
      cam_lka_steering_cmd_counter=0,
      pt_lka_steering_cmd_counter=2,
      loopback_lka_steering_cmd_updated=False,
      loopback_lka_steering_cmd_ts_nanos=0,
      lkas_rejected=0,
      buttons_counter=0,
    )

    controller.frame = 3
    _, first = controller.update(CC.as_reader(), structs.CarControlSP(), CS, 20_000_000)
    self.assertTrue(any(msg[0] == 0x180 for msg in first))
    self.assertEqual(controller.lka_steering_cmd_counter, 3)

    CS.loopback_lka_steering_cmd_updated = True
    CS.loopback_lka_steering_cmd_ts_nanos = 20_000_000
    controller.frame = 6
    _, too_soon = controller.update(CC.as_reader(), structs.CarControlSP(), CS, 30_000_000)
    self.assertFalse(any(msg[0] == 0x180 for msg in too_soon))

    CS.loopback_lka_steering_cmd_updated = False
    controller.frame = 9
    _, spaced = controller.update(CC.as_reader(), structs.CarControlSP(), CS, 40_000_000)
    self.assertTrue(any(msg[0] == 0x180 for msg in spaced))
