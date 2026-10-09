from opendbc.can import CANDefine, CANParser
from opendbc.car import Bus, DT_CTRL, create_button_events, structs, uds
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.interfaces import CarStateBase
from opendbc.car.mazda.values import DBC, LKAS_LIMITS, CarControllerParams, MazdaFlags
from opendbc.sunnypilot.car.mazda.carstate_ext import CarStateExt

ButtonType = structs.CarState.ButtonEvent.Type

FSC_SETTLE_FRAMES = int(CarControllerParams.FSC_SETTLE_T / DT_CTRL)
STOCK_RADAR_ALIVE_FRAMES = int(CarControllerParams.STOCK_RADAR_ALIVE_T / DT_CTRL)
STOCK_RADAR_GUARD_FRAMES = round(CarControllerParams.STOCK_RADAR_GUARD_T / DT_CTRL)
MAIN_OFF_DEBOUNCE_SAMPLES = round(CarControllerParams.MAIN_OFF_DEBOUNCE_T * 100)
CAM_LANEINFO_FRESH_FRAMES = int(CarControllerParams.CAM_LANEINFO_FRESH_T / DT_CTRL)
MAIN_CAN_WITNESSES = {"PEDALS": ("ACC_ACTIVE", round(0.2 / DT_CTRL)), "ENGINE_DATA": ("SPEED", round(0.1 / DT_CTRL))}
HOLD_STATE_HOLDING = 3


def body_holds(pt) -> bool:
  return pt["EPB"]["HOLD_STATE"] == HOLD_STATE_HOLDING or pt["GEAR"]["BRAKE_HOLD"] == 1


class CarState(CarStateBase, CarStateExt):
  def __init__(self, CP, CP_SP):
    CarStateBase.__init__(self, CP, CP_SP)
    CarStateExt.__init__(self, CP, CP_SP)

    can_define = CANDefine(DBC[CP.carFingerprint][Bus.pt])
    self.shifter_values = can_define.dv["GEAR"]["GEAR"]

    self.crz_btns_counter = 0
    self.acc_active_last = False
    self.lkas_allowed_speed = False

    self.params = CarControllerParams(CP)
    self.lkas_blocked = False
    self.lkas_effective = 0
    self.lkas_track_state = False
    self.steer_undelivered_frames = 0
    self.steer_undelivered = False
    self.steer_undelivered_alert = False
    self.lkas_block_origin_speed: float | None = None
    self.lkas_delivered = False
    self.steer_first_engage_hold = False
    self.lkas_rejected = 0

    self.distance_button = 0
    self.accel_button = 0
    self.decel_button = 0
    self.cancel_button = 0
    self.resume_button = 0
    self.main_button = 0

    self.cruise_available = False
    self.cruise_enabled = False
    self.mrcc_armed_raw = False
    self.cruise_enabled_blocked = True
    self.stock_radar_silent_frames = 0
    self.stock_radar_seen = False
    self.main_can_silent_frames = {name: fresh for name, (_, fresh) in MAIN_CAN_WITNESSES.items()}
    self.radar_bus_healthy = False
    self.radar_control_active = False
    self.radar_owned = False
    self.radar_restore_failed = False
    self.radar_handback_active = False
    self.radar_was_silenced = False
    self.main_off_samples = 0
    self.radar_session_refused = False
    self.radar_session_response = 0
    self.fsc_settled_frames = 0
    self.body_hold = False
    self.hbc_request = False
    self.cam_laneinfo_seen = False
    self.cam_laneinfo_silent_frames = CAM_LANEINFO_FRESH_FRAMES

  @property
  def fsc_settled(self) -> bool:
    return self.fsc_settled_frames >= FSC_SETTLE_FRAMES

  @property
  def stock_radar_alive(self) -> bool:
    return self.stock_radar_seen and self.stock_radar_silent_frames < STOCK_RADAR_ALIVE_FRAMES

  @property
  def stock_radar_gone(self) -> bool:
    return self.radar_bus_healthy and self.stock_radar_silent_frames >= STOCK_RADAR_GUARD_FRAMES

  def update_steer_undelivered(self, v_ego_raw: float, lkas_request: float) -> None:
    self.lkas_delivered |= self.lkas_effective != 0
    self.steer_first_engage_hold = (not self.lkas_delivered and self.lkas_blocked and self.lkas_track_state and
                                    v_ego_raw < self.params.STEER_UNDELIVERED_ALERT_ORIGIN_SPEED)

    if not self.lkas_blocked:
      self.steer_undelivered_frames = 0
      self.steer_undelivered = False
      self.steer_undelivered_alert = False
      self.lkas_block_origin_speed = None
      return

    if self.lkas_block_origin_speed is None:
      self.lkas_block_origin_speed = v_ego_raw

    if not self.steer_undelivered:
      if self.lkas_effective == 0 and abs(lkas_request) > self.params.STEER_UNDELIVERED_MIN:
        self.steer_undelivered_frames += 1
        self.steer_undelivered = self.steer_undelivered_frames >= self.params.STEER_UNDELIVERED_FRAMES
      else:
        self.steer_undelivered_frames = 0
    else:
      # The controller deliberately commands zero after the protection latch trips. Keep timing
      # the EPS block itself so the driver warning can arm independently of the now-zero request.
      self.steer_undelivered_frames += 1

    alert_frames = self.params.STEER_UNDELIVERED_FRAMES + self.params.STEER_UNDELIVERED_ALERT_FRAMES
    self.steer_undelivered_alert = (
      self.steer_undelivered
      and self.steer_undelivered_frames >= alert_frames
      and v_ego_raw >= self.params.STEER_UNDELIVERED_ALERT_MIN_SPEED
      and self.lkas_block_origin_speed >= self.params.STEER_UNDELIVERED_ALERT_ORIGIN_SPEED
      and not self.lkas_track_state
    )

  def update(self, can_parsers) -> tuple[structs.CarState, structs.CarStateSP]:
    cp = can_parsers[Bus.pt]
    cp_cam = can_parsers[Bus.cam]

    ret = structs.CarState()
    ret_sp = structs.CarStateSP()

    self.parse_wheel_speeds(ret,
      cp.vl["WHEEL_SPEEDS"]["FL"],
      cp.vl["WHEEL_SPEEDS"]["FR"],
      cp.vl["WHEEL_SPEEDS"]["RL"],
      cp.vl["WHEEL_SPEEDS"]["RR"],
    )

    # Match panda speed reading
    speed_kph = cp.vl["ENGINE_DATA"]["SPEED"]
    ret.standstill = speed_kph <= .1

    can_gear = int(cp.vl["GEAR"]["GEAR"])
    ret.gearShifter = self.parse_gear_shifter(self.shifter_values.get(can_gear, None))
    self.body_hold = body_holds(cp.vl)

    ret.genericToggle = bool(cp.vl["BLINK_INFO"]["HIGH_BEAMS"])
    ret.leftBlindspot = cp.vl["BSM"]["LEFT_BS_STATUS"] != 0
    ret.rightBlindspot = cp.vl["BSM"]["RIGHT_BS_STATUS"] != 0
    ret.leftBlinker, ret.rightBlinker = self.update_blinker_from_lamp(40, cp.vl["BLINK_INFO"]["LEFT_BLINK"] == 1,
                                                                      cp.vl["BLINK_INFO"]["RIGHT_BLINK"] == 1)

    ret.steeringAngleDeg = cp.vl["STEER"]["STEER_ANGLE"]
    ret.steeringTorque = cp.vl["STEER_TORQUE"]["STEER_TORQUE_SENSOR"]
    ret.steeringPressed = abs(ret.steeringTorque) > LKAS_LIMITS.STEER_THRESHOLD

    ret.steeringTorqueEps = cp.vl["STEER_TORQUE"]["STEER_TORQUE_MOTOR"]
    ret.steeringRateDeg = cp.vl["STEER_RATE"]["STEER_ANGLE_RATE"]

    ret.brakePressed = cp.vl["PEDALS"]["BRAKE_ON"] == 1

    ret.seatbeltUnlatched = cp.vl["SEATBELT"]["DRIVER_SEATBELT"] == 0
    ret.doorOpen = any([cp.vl["DOORS"]["FL"], cp.vl["DOORS"]["FR"],
                        cp.vl["DOORS"]["BL"], cp.vl["DOORS"]["BR"]])

    # TODO: this should be from 0 - 1.
    ret.gasPressed = cp.vl["ENGINE_DATA"]["PEDAL_GAS"] > 0

    # Either due to low speed or hands off on legacy firmware.
    lkas_blocked = cp.vl["STEER_RATE"]["LKAS_BLOCK"] == 1
    self.lkas_blocked = lkas_blocked
    self.lkas_effective = cp.vl["STEER_RATE"]["LKAS_EFFECTIVE"]
    self.lkas_track_state = cp.vl["STEER_RATE"]["LKAS_TRACK_STATE"] == 1
    self.lkas_rejected = sum(1 for request in can_parsers[Bus.loopback].vl_all["CAM_LKAS"]["LKAS_REQUEST"] if request != 0)

    if self.CP.flags & MazdaFlags.STEER_TO_ZERO_EPS:
      self.update_steer_undelivered(ret.vEgoRaw, cp.vl["STEER_RATE"]["LKAS_REQUEST"])
      self.lkas_allowed_speed = True
    else:
      # LKAS is enabled at 52kph going up and disabled at 45kph going down.
      if speed_kph > LKAS_LIMITS.ENABLE_SPEED and not lkas_blocked:
        self.lkas_allowed_speed = True
      elif speed_kph < LKAS_LIMITS.DISABLE_SPEED:
        self.lkas_allowed_speed = False

    # Track camera freshness for the cold-start radar-presence guard.
    if len(cp_cam.vl_all["CAM_LANEINFO"]["LANE_LINES"]) > 0:
      self.cam_laneinfo_seen = True
      self.cam_laneinfo_silent_frames = 0
    else:
      self.cam_laneinfo_silent_frames += 1
    cam_laneinfo_fresh = self.cam_laneinfo_seen and self.cam_laneinfo_silent_frames < CAM_LANEINFO_FRESH_FRAMES

    acc_armed = cp.vl["PEDALS"]["ACC_OFF"] == 1
    acc_active = cp.vl["PEDALS"]["ACC_ACTIVE"] == 1
    self.mrcc_armed_raw = acc_armed or acc_active

    if self.CP.openpilotLongitudinalControl:
      # Once the stock radar is silent, PEDALS becomes the authoritative MRCC/main state.
      pedals = cp.vl_all["PEDALS"]
      for off, active in zip(pedals["ACC_OFF"], pedals["ACC_ACTIVE"], strict=True):
        if off or active:
          self.cruise_available = True
          self.main_off_samples = 0
        else:
          self.main_off_samples = min(self.main_off_samples + 1, MAIN_OFF_DEBOUNCE_SAMPLES)
          if self.main_off_samples >= MAIN_OFF_DEBOUNCE_SAMPLES:
            self.cruise_available = False
      self.cruise_enabled = acc_active

      # Distinguish a silenced radar from a dead vehicle bus before assuming ownership.
      self.radar_bus_healthy = True
      for name, (signal, fresh) in MAIN_CAN_WITNESSES.items():
        silent = 0 if len(cp.vl_all[name][signal]) > 0 else min(self.main_can_silent_frames[name] + 1, fresh)
        self.main_can_silent_frames[name] = silent
        self.radar_bus_healthy &= silent < fresh
      if len(cp.vl_all["CRZ_INFO"]["CTR"]) > 0:
        self.stock_radar_seen = True
        self.stock_radar_silent_frames = 0
      elif self.radar_bus_healthy:
        self.stock_radar_silent_frames += 1
      else:
        self.stock_radar_silent_frames = STOCK_RADAR_ALIVE_FRAMES

      # Validate single-frame UDS session replies from the radar.
      resp = cp.vl_all["RADAR_UDS_RESPONSE"]
      self.radar_session_refused = False
      self.radar_session_response = 0
      for pci, sid, sub, nrc in zip(resp["PCI"], resp["SID"], resp["SUB"], resp["NRC"], strict=True):
        if pci == 3 and sid == 0x7F and sub == uds.SERVICE_TYPE.DIAGNOSTIC_SESSION_CONTROL and nrc != 0x78:
          self.radar_session_refused = True
        elif pci == 6 and sid == 0x50 and sub in (1, 2):
          self.radar_session_response = int(sub)

      silenced = self.radar_control_active and not self.stock_radar_alive and (self.stock_radar_gone or self.radar_was_silenced)
      ret.accFaulted = self.radar_restore_failed or (self.radar_was_silenced and self.stock_radar_alive and not self.radar_handback_active)
      self.radar_was_silenced |= silenced
      self.radar_owned = silenced

      if not silenced:
        self.cruise_enabled_blocked = True
      elif not self.cruise_enabled:
        self.cruise_enabled_blocked = False

      ret.cruiseState.available = self.cruise_available
      ret.cruiseState.enabled = self.cruise_enabled and not self.cruise_enabled_blocked

      laneinfo = cp_cam.vl["CAM_LANEINFO"]
      settled = cam_laneinfo_fresh and not (laneinfo["NO_ERR_BIT"] or laneinfo["ERR_BIT"])
      self.fsc_settled_frames = self.fsc_settled_frames + 1 if settled else 0
    else:
      ret.cruiseState.available = cp.vl["CRZ_CTRL"]["CRZ_AVAILABLE"] == 1
      ret.cruiseState.enabled = cp.vl["CRZ_CTRL"]["CRZ_ACTIVE"] == 1

    # PEDALS.STANDSTILL is wheel stop, not the alpha-long hold state.
    ret.cruiseState.standstill = cp.vl["PEDALS"]["STANDSTILL"] == 1 and not self.CP.openpilotLongitudinalControl
    ret.cruiseState.speed = cp.vl["CRZ_EVENTS"]["CRZ_SPEED"] * CV.KPH_TO_MS

    # stock lkas should be on
    ret.invalidLkasSetting = cp_cam.vl["CAM_LANEINFO"]["LANE_LINES"] == 0

    if ret.cruiseState.enabled:
      if not self.lkas_allowed_speed and self.acc_active_last:
        self.low_speed_alert = True
      else:
        self.low_speed_alert = False
    ret.lowSpeedAlert = self.low_speed_alert

    if self.CP.flags & MazdaFlags.STEER_TO_ZERO_EPS:
      # LKAS_BLOCK alone is normal on this EPS at low speed. Only report a temporary fault after
      # sustained, filtered road-speed non-delivery; the controller protection has already fired.
      ret.steerFaultTemporary = self.steer_undelivered_alert
    else:
      ret.steerFaultTemporary = self.lkas_allowed_speed and lkas_blocked

    self.acc_active_last = ret.cruiseState.enabled

    self.crz_btns_counter = cp.vl["CRZ_BTNS"]["CTR"]

    # camera signals
    self.cam_lkas = cp_cam.vl["CAM_LKAS"]
    self.cam_laneinfo = cp_cam.vl["CAM_LANEINFO"]
    self.hbc_request = cam_laneinfo_fresh and self.cam_laneinfo["BIT2"] == 1
    ret.steerFaultPermanent = cp_cam.vl["CAM_LKAS"]["ERR_BIT_1"] == 1

    # Cruise-control button events. SET_P/SET_M are the physical set-speed buttons; RES is a
    # distinct resume command and must not be mistaken for SET+ while the ICBM servo is active.
    prev_distance_button = self.distance_button
    prev_accel_button = self.accel_button
    prev_decel_button = self.decel_button
    prev_cancel_button = self.cancel_button
    prev_resume_button = self.resume_button
    prev_main_button = self.main_button
    self.distance_button = cp.vl["CRZ_BTNS"]["DISTANCE_LESS"]
    self.accel_button = cp.vl["CRZ_BTNS"]["SET_P"]
    self.decel_button = cp.vl["CRZ_BTNS"]["SET_M"]
    self.cancel_button = cp.vl["CRZ_BTNS"]["CAN_OFF"]
    self.resume_button = cp.vl["CRZ_BTNS"]["RES"]
    self.main_button = int(cp.vl["CRZ_BTNS"]["MODE_X"] == 1 or cp.vl["CRZ_BTNS"]["MODE_Y"] == 1)

    ret.buttonEvents = [
      *create_button_events(self.distance_button, prev_distance_button, {1: ButtonType.gapAdjustCruise}),
      *create_button_events(self.accel_button, prev_accel_button, {1: ButtonType.accelCruise}),
      *create_button_events(self.decel_button, prev_decel_button, {1: ButtonType.decelCruise}),
      *create_button_events(self.cancel_button, prev_cancel_button, {1: ButtonType.cancel}),
      *create_button_events(self.resume_button, prev_resume_button, {1: ButtonType.resumeCruise}),
      *create_button_events(self.main_button, prev_main_button, {1: ButtonType.mainCruise}),
    ]

    CarStateExt.update(self, ret, ret_sp, can_parsers)

    return ret, ret_sp

  @staticmethod
  def get_can_parsers(CP, CP_SP):
    pt_messages = [("EPB", float("nan"))]
    if CP.openpilotLongitudinalControl:
      pt_messages += [("CRZ_INFO", float("nan")), ("RADAR_UDS_RESPONSE", float("nan"))]
    cam_messages = [("CAM_LANEINFO", float("nan")), ("CAM_TRAFFIC_SIGNS", float("nan"))]
    return {
      Bus.pt: CANParser(DBC[CP.carFingerprint][Bus.pt], pt_messages, 0),
      Bus.cam: CANParser(DBC[CP.carFingerprint][Bus.pt], cam_messages, 2),
      # Panda reports rejected bus-0 transmissions back on bus 192. This traffic is sporadic,
      # so it must never participate in parser validity or timeout checks.
      Bus.loopback: CANParser(DBC[CP.carFingerprint][Bus.pt], [("CAM_LKAS", float("nan"))], 192),
    }
