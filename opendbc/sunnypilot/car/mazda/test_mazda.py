import unittest
from itertools import pairwise
from types import SimpleNamespace
from unittest.mock import patch

from opendbc.can import CANPacker, CANParser
from opendbc.car import Bus, structs
from opendbc.car.car_helpers import interfaces
from opendbc.car.mazda import mazdacan
from opendbc.car.mazda.carcontroller import CarController
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


class TestMazdaPandaRejectionRecovery(unittest.TestCase):
  def setUp(self):
    self.CP = interfaces[CAR.MAZDA_CX9].get_non_essential_params(CAR.MAZDA_CX9)
    self.CP.flags = int(self.CP.flags | MazdaFlags.STEER_TO_ZERO_EPS)
    self.CP_SP = interfaces[CAR.MAZDA_CX9].get_non_essential_params_sp(self.CP, CAR.MAZDA_CX9)
    self.packer = CANPacker("mazda_2017")

  def rejected_steer(self, torque, bus=192, frame=0):
    msg = mazdacan.create_steering_control(
      self.packer, self.CP, frame, torque, {"BIT_1": 0, "ERR_BIT_1": 0, "ERR_BIT_2": 0},
    )
    return msg[0], msg[1], bus

  def test_carstate_counts_only_nonzero_panda_rejections(self):
    car_state = CarState(self.CP, self.CP_SP)
    parsers = car_state.get_can_parsers(self.CP, self.CP_SP)
    loopback = parsers[Bus.loopback]

    loopback.update([1, [self.rejected_steer(12), self.rejected_steer(-12, frame=1), self.rejected_steer(0, frame=2)]])
    car_state.update(parsers)
    self.assertEqual(car_state.lkas_rejected, 2)

    for bus in (0, 2, 128):
      loopback.update([2, [self.rejected_steer(12, bus=bus)]])
      car_state.update(parsers)
      self.assertEqual(car_state.lkas_rejected, 0)

    loopback.update([3, []])
    car_state.update(parsers)
    self.assertEqual(car_state.lkas_rejected, 0)

  def test_loopback_parser_does_not_affect_can_validity(self):
    loopback = CarState.get_can_parsers(self.CP, self.CP_SP)[Bus.loopback]
    self.assertTrue(loopback.can_valid)
    loopback.update([10_000_000_000, []])
    self.assertFalse(loopback.bus_timeout)
    self.assertTrue(loopback.can_valid)

  def test_rejected_steer_restarts_ramp_from_zero(self):
    controller = CarController({Bus.pt: "mazda_2017"}, self.CP, self.CP_SP)
    controller.frame = 1  # Keep this test focused on steering rather than the periodic HUD frame.

    CC = structs.CarControl(latActive=True)
    CC.actuators.torque = 1.0
    CS = SimpleNamespace(
      out=SimpleNamespace(vEgoRaw=10.0, steeringTorque=0.0, brakePressed=False),
      steer_undelivered=False,
      steer_first_engage_hold=False,
      lkas_rejected=0,
      crz_btns_counter=0,
      cam_lkas={"BIT_1": 0, "ERR_BIT_1": 0, "ERR_BIT_2": 0},
      cam_laneinfo={
        "LINE_VISIBLE": 0, "LINE_NOT_VISIBLE": 0, "LANE_LINES": 0,
        "BIT1": 0, "BIT2": 0, "BIT3": 0, "NO_ERR_BIT": 0, "S1": 0, "S1_HBEAM": 0,
      },
      lkas_allowed_speed=True,
      accel_button=0,
      decel_button=0,
    )

    CC_SP = structs.CarControlSP()
    first, _ = controller.update(CC.as_reader(), CC_SP, CS, 0)
    self.assertEqual(first.torqueOutputCan, controller.params.STEER_DELTA_UP)

    CS.lkas_rejected = 1
    recovered, _ = controller.update(CC.as_reader(), CC_SP, CS, 0)

    self.assertEqual(controller.apply_torque_last, controller.params.STEER_DELTA_UP)
    self.assertEqual(recovered.torqueOutputCan, controller.params.STEER_DELTA_UP)


class TestMazdaDonorSteering(unittest.TestCase):
  def setUp(self):
    self.CP = interfaces[CAR.MAZDA_CX9].get_non_essential_params(CAR.MAZDA_CX9)
    self.CP.flags = int(self.CP.flags | MazdaFlags.STEER_TO_ZERO_EPS)
    self.CP_SP = interfaces[CAR.MAZDA_CX9].get_non_essential_params_sp(self.CP, CAR.MAZDA_CX9)
    self.CS = CarState(self.CP, self.CP_SP)
    self.controller = CarController({Bus.pt: "mazda_2017"}, self.CP, self.CP_SP)
    self.controller.frame = 1  # Avoid the periodic HUD frame in controller-focused tests.
    self.CC_SP = structs.CarControlSP()
    self.can_parser = CANParser("mazda_2017", [("CAM_LKAS", 100)], 0)
    self.controller_state = SimpleNamespace(
      out=SimpleNamespace(vEgoRaw=10.0, steeringTorque=0.0, brakePressed=False),
      steer_undelivered=False,
      steer_first_engage_hold=False,
      lkas_rejected=0,
      crz_btns_counter=0,
      cam_lkas={"BIT_1": 0, "ERR_BIT_1": 0, "ERR_BIT_2": 0},
      cam_laneinfo={
        "LINE_VISIBLE": 0, "LINE_NOT_VISIBLE": 0, "LANE_LINES": 0,
        "BIT1": 0, "BIT2": 0, "BIT3": 0, "NO_ERR_BIT": 0, "S1": 0, "S1_HBEAM": 0,
      },
      lkas_allowed_speed=True,
      accel_button=0,
      decel_button=0,
    )

  def update_delivery(self, *, blocked, effective, request, track=False, speed=10.0):
    self.CS.lkas_blocked = blocked
    self.CS.lkas_effective = effective
    self.CS.lkas_track_state = track
    self.CS.update_steer_undelivered(speed, request)

  def controller_update(self, *, lat_active, torque):
    CC = structs.CarControl(latActive=lat_active)
    CC.actuators.torque = torque
    actuators, sends = self.controller.update(CC.as_reader(), self.CC_SP, self.controller_state, 0)
    steer = next(msg for msg in sends if msg[0] == 0x243)
    self.can_parser.update([self.controller.frame, [steer]])
    return actuators, int(self.can_parser.vl["CAM_LKAS"]["LKAS_REQUEST"]), sends

  def test_lkas_block_alone_is_not_undelivered_evidence(self):
    for _ in range(self.CS.params.STEER_UNDELIVERED_FRAMES * 2):
      self.update_delivery(blocked=True, effective=1, request=600)
    self.assertFalse(self.CS.steer_undelivered)
    self.assertEqual(self.CS.steer_undelivered_frames, 0)

  def test_undelivered_threshold_and_duration(self):
    for request in (-self.CS.params.STEER_UNDELIVERED_MIN, 0, self.CS.params.STEER_UNDELIVERED_MIN):
      for _ in range(self.CS.params.STEER_UNDELIVERED_FRAMES + 1):
        self.update_delivery(blocked=True, effective=0, request=request)
      self.assertFalse(self.CS.steer_undelivered)
      self.assertEqual(self.CS.steer_undelivered_frames, 0)

    request = self.CS.params.STEER_UNDELIVERED_MIN + 1
    for _ in range(self.CS.params.STEER_UNDELIVERED_FRAMES - 1):
      self.update_delivery(blocked=True, effective=0, request=request)
    self.assertFalse(self.CS.steer_undelivered)
    self.update_delivery(blocked=True, effective=0, request=request)
    self.assertTrue(self.CS.steer_undelivered)

  def test_partial_or_sign_mismatched_effective_torque_clears_count(self):
    for _ in range(self.CS.params.STEER_UNDELIVERED_FRAMES - 1):
      self.update_delivery(blocked=True, effective=0, request=600)
    self.assertGreater(self.CS.steer_undelivered_frames, 0)

    # The EPS ramps and rate limits independently. Any nonzero feedback proves delivery;
    # sign or magnitude mismatch alone is deliberately not rejection evidence.
    self.update_delivery(blocked=True, effective=-1, request=600)
    self.assertFalse(self.CS.steer_undelivered)
    self.assertEqual(self.CS.steer_undelivered_frames, 0)

  def test_undelivered_latch_clears_only_when_block_clears(self):
    for _ in range(self.CS.params.STEER_UNDELIVERED_FRAMES):
      self.update_delivery(blocked=True, effective=0, request=600)
    self.assertTrue(self.CS.steer_undelivered)

    self.update_delivery(blocked=True, effective=0, request=0)
    self.assertTrue(self.CS.steer_undelivered)
    self.update_delivery(blocked=False, effective=0, request=0)
    self.assertFalse(self.CS.steer_undelivered)
    self.assertFalse(self.CS.steer_undelivered_alert)
    self.assertEqual(self.CS.steer_undelivered_frames, 0)

  def test_undelivered_alert_after_sustained_at_speed_dropout(self):
    params = self.CS.params
    total_frames = params.STEER_UNDELIVERED_FRAMES + params.STEER_UNDELIVERED_ALERT_FRAMES
    request = params.STEER_UNDELIVERED_MIN + 1
    speed = params.STEER_UNDELIVERED_ALERT_MIN_SPEED + 1.0

    for _ in range(total_frames - 1):
      self.update_delivery(blocked=True, effective=0, request=request, track=False, speed=speed)

    self.assertTrue(self.CS.steer_undelivered)
    self.assertFalse(self.CS.steer_undelivered_alert)

    self.update_delivery(blocked=True, effective=0, request=request, track=False, speed=speed)
    self.assertTrue(self.CS.steer_undelivered_alert)

  def test_undelivered_alert_suppressed_for_low_speed_origin(self):
    params = self.CS.params
    request = params.STEER_UNDELIVERED_MIN + 1

    self.update_delivery(blocked=True, effective=0, request=request, track=True, speed=0.3)
    for _ in range(params.STEER_UNDELIVERED_FRAMES + params.STEER_UNDELIVERED_ALERT_FRAMES + 10):
      self.update_delivery(
        blocked=True,
        effective=0,
        request=request,
        track=False,
        speed=params.STEER_UNDELIVERED_ALERT_MIN_SPEED + 2.0,
      )

    self.assertTrue(self.CS.steer_undelivered)
    self.assertFalse(self.CS.steer_undelivered_alert)

  def test_undelivered_alert_suppressed_by_track_state(self):
    params = self.CS.params
    total_frames = params.STEER_UNDELIVERED_FRAMES + params.STEER_UNDELIVERED_ALERT_FRAMES
    request = params.STEER_UNDELIVERED_MIN + 1
    speed = params.STEER_UNDELIVERED_ALERT_MIN_SPEED + 1.0

    for _ in range(total_frames):
      self.update_delivery(blocked=True, effective=0, request=request, track=True, speed=speed)

    self.assertTrue(self.CS.steer_undelivered)
    self.assertFalse(self.CS.steer_undelivered_alert)

    self.update_delivery(blocked=True, effective=0, request=request, track=False, speed=speed)
    self.assertTrue(self.CS.steer_undelivered_alert)

  def test_first_engage_hold_low_speed_entry_and_exit(self):
    self.update_delivery(blocked=True, effective=0, request=0, track=True, speed=0.3)
    self.assertTrue(self.CS.steer_first_engage_hold)

    self.update_delivery(blocked=True, effective=0, request=0, track=False, speed=0.3)
    self.assertFalse(self.CS.steer_first_engage_hold)
    self.update_delivery(blocked=True, effective=1, request=1, track=True, speed=0.3)
    self.assertFalse(self.CS.steer_first_engage_hold)

  def test_disabled_lateral_sends_only_zero_steering(self):
    for _ in range(10):
      actuators, request, sends = self.controller_update(lat_active=True, torque=1.0)
    self.assertGreater(actuators.torqueOutputCan, 0)
    self.assertGreater(request, 0)

    actuators, request, sends = self.controller_update(lat_active=False, torque=1.0)
    self.assertEqual(actuators.torqueOutputCan, 0)
    self.assertEqual(request, 0)
    self.assertEqual(sum(msg[0] == 0x243 for msg in sends), 1)
    self.assertEqual(self.controller.apply_torque_last, 0)

  def test_maximum_rate_sign_change_and_reenable(self):
    params = self.controller.params
    self.controller_state.out.vEgoRaw = 0.0
    eps_ceiling = params.EPS_CEILING_LOOKUP[1][0]

    positive = []
    for _ in range(eps_ceiling // params.STEER_DELTA_UP + 5):
      actuators, request, _ = self.controller_update(lat_active=True, torque=1.0)
      positive.append(request)
    self.assertEqual(max(positive), eps_ceiling)
    self.assertLess(eps_ceiling, params.STEER_MAX)
    self.assertTrue(all(0 <= b - a <= params.STEER_DELTA_UP for a, b in pairwise(positive)))

    previous = positive[-1]
    while previous > 0:
      _, request, _ = self.controller_update(lat_active=True, torque=-1.0)
      self.assertLessEqual(previous - request, params.STEER_DELTA_DOWN)
      previous = request
    self.assertGreaterEqual(previous, -params.STEER_DELTA_UP)

    self.controller_update(lat_active=False, torque=-1.0)
    _, request, _ = self.controller_update(lat_active=True, torque=-1.0)
    self.assertEqual(request, -params.STEER_DELTA_UP)


if __name__ == "__main__":
  unittest.main()
