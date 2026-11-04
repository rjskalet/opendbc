import pytest

from opendbc.car import gen_empty_fingerprint, structs
from opendbc.car.mazda.interface import CarInterface, STANDARD_RADAR_TRACK_ADDRS
from opendbc.car.mazda.values import CAR, MazdaFlags, MazdaSafetyFlags


DONOR_EPS_FW = b'KSD5-3210X-C-00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
CX9_RADAR_FW = b'K123-67XK2-F\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'


def car_fw(ecu, address, version):
  fw = structs.CarParams.CarFw()
  fw.ecu = ecu
  fw.address = address
  fw.subAddress = 0
  fw.fwVersion = version
  return fw


def cx9_fw(donor_eps=True):
  eps = DONOR_EPS_FW if donor_eps else b'KJ01-3210X-L-00' + b'\x00' * 9
  return [
    car_fw(structs.CarParams.Ecu.eps, 0x730, eps),
    car_fw(structs.CarParams.Ecu.fwdRadar, 0x764, CX9_RADAR_FW),
  ]


def fingerprint_with_tracks(count=6):
  fp = gen_empty_fingerprint()
  for addr in sorted(STANDARD_RADAR_TRACK_ADDRS)[:count]:
    fp[0][addr] = 8
  return fp


def params(fp, fw, alpha_long=True):
  return CarInterface.get_params(CAR.MAZDA_CX9, fp, fw, alpha_long=alpha_long, is_release=False, docs=False)


def test_cx9_donor_eps_and_observed_standard_tracks_enable_alpha_long():
  cp = params(fingerprint_with_tracks(), cx9_fw())

  assert cp.flags & MazdaFlags.STEER_TO_ZERO_EPS
  assert not cp.flags & MazdaFlags.G46L_RADAR
  assert cp.alphaLongitudinalAvailable
  assert cp.openpilotLongitudinalControl
  assert cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.LONG


@pytest.mark.parametrize("track_count", [0, 1, 5])
def test_cx9_incomplete_standard_track_stream_stays_stock_long(track_count):
  cp = params(fingerprint_with_tracks(track_count), cx9_fw())

  assert cp.flags & MazdaFlags.STEER_TO_ZERO_EPS
  assert not cp.alphaLongitudinalAvailable
  assert not cp.openpilotLongitudinalControl
  assert not cp.safetyConfigs[0].safetyParam & MazdaSafetyFlags.LONG


def test_cx9_standard_tracks_do_not_bypass_eps_gate():
  cp = params(fingerprint_with_tracks(), cx9_fw(donor_eps=False))

  assert not cp.flags & MazdaFlags.STEER_TO_ZERO_EPS
  assert not cp.alphaLongitudinalAvailable
  assert not cp.openpilotLongitudinalControl
