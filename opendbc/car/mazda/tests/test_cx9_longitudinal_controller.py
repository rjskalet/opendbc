import pytest

from opendbc.car import Bus, gen_empty_fingerprint, structs
from opendbc.car.mazda.carcontroller import CarController
from opendbc.car.mazda.carstate import CarState, FSC_SETTLE_FRAMES, STOCK_RADAR_GUARD_FRAMES
from opendbc.car.mazda.interface import CarInterface, STANDARD_RADAR_TRACK_ADDRS
from opendbc.car.mazda.values import CAR


DONOR_EPS_FW = b'KSD5-3210X-C-00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
CX9_RADAR_FW = b'K123-67XK2-F\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'


def fw(ecu, address, version):
  out = structs.CarParams.CarFw()
  out.ecu = ecu
  out.address = address
  out.subAddress = 0
  out.fwVersion = version
  return out


def build():
  fp = gen_empty_fingerprint()
  for addr in STANDARD_RADAR_TRACK_ADDRS:
    fp[0][addr] = 8

  car_fw = [
    fw(structs.CarParams.Ecu.eps, 0x730, DONOR_EPS_FW),
    fw(structs.CarParams.Ecu.fwdRadar, 0x764, CX9_RADAR_FW),
  ]
  cp = CarInterface.get_params(CAR.MAZDA_CX9, fp, car_fw, alpha_long=True, is_release=False, docs=False)
  cp_sp = CarInterface.get_params_sp(cp, CAR.MAZDA_CX9, fp, car_fw, alpha_long=True, is_release_sp=False, docs=False)
  assert cp.openpilotLongitudinalControl

  controller = CarController({Bus.pt: "mazda_2017"}, cp, cp_sp)
  cs = CarState(cp, cp_sp)
  cs.out = structs.CarState()
  cs.out.canValid = True
  cs.out.standstill = False
  cs.out.gasPressed = False
  cs.out.brakePressed = False
  cs.out.vEgoRaw = 15.0
  cs.cruise_available = True
  cs.cruise_enabled = True
  cs.radar_bus_healthy = True
  cs.stock_radar_seen = True
  cs.stock_radar_silent_frames = STOCK_RADAR_GUARD_FRAMES
  cs.fsc_settled_frames = FSC_SETTLE_FRAMES
  cs.body_hold = False
  cs.hbc_request = False

  cc = structs.CarControl()
  cc.enabled = True
  cc.longActive = True
  cc.actuators.accel = 0.5
  cc.actuators.longControlState = structs.CarControl.Actuators.LongControlState.pid
  cc.hudControl.leadVisible = False
  cc.hudControl.leadDistanceBars = 2

  cc_sp = structs.CarControlSP()
  cc_sp.stockEcuHandBack = False
  cc_sp.leadOne.dRel = 40.0
  cc_sp.leadOne.vRel = 0.0
  return controller, cs, cc.as_reader(), cc_sp


def step(controller, cs, cc, cc_sp):
  sends = controller.update_longitudinal(cc, cc_sp, cs)
  controller.frame += 1
  return sends


def test_cx9_standard_dialect_emits_expected_longitudinal_cadence():
  controller, cs, cc, cc_sp = build()
  counts = {0x21b: 0, 0x21c: 0, 0x499: 0, 0x764: 0}
  track_counts = {addr: 0 for addr in STANDARD_RADAR_TRACK_ADDRS}

  for _ in range(100):
    sends = step(controller, cs, cc, cc_sp)
    for addr, _, bus in sends:
      if addr in counts:
        counts[addr] += 1
      if addr in track_counts:
        track_counts[addr] += 1

    # Whenever the acceleration/state frames are emitted, each is duplicated to car and camera.
    info_buses = sorted(bus for addr, _, bus in sends if addr == 0x21b)
    ctrl_buses = sorted(bus for addr, _, bus in sends if addr == 0x21c)
    if info_buses:
      assert info_buses == [0, 2]
      assert ctrl_buses == [0, 2]

  assert counts[0x21b] == 100
  assert counts[0x21c] == 100
  assert counts[0x499] == 20
  assert counts[0x764] == 2
  assert set(track_counts.values()) == {20}
  assert controller.long_counter == 50
  assert controller.radar_counter == 10


def test_cx9_standard_dialect_uses_standard_tracks_not_g46l():
  controller, cs, cc, cc_sp = build()
  assert not controller.g46l

  sends = step(controller, cs, cc, cc_sp)
  addrs = {addr for addr, _, _ in sends}
  assert 0x499 in addrs
  assert STANDARD_RADAR_TRACK_ADDRS.issubset(addrs)


def test_cx9_longitudinal_command_stays_inside_zoompilot_bounds():
  controller, cs, _, cc_sp = build()

  cc = structs.CarControl()
  cc.enabled = True
  cc.longActive = True
  cc.actuators.accel = 4.0
  cc.actuators.longControlState = structs.CarControl.Actuators.LongControlState.pid
  cc.hudControl.leadVisible = False
  cc.hudControl.leadDistanceBars = 2

  for _ in range(300):
    step(controller, cs, cc.as_reader(), cc_sp)

  # At 15 m/s the positive command is additionally shaped below the ISO +2.0 m/s² bound.
  assert 0.0 < controller.accel_last <= 1.05
