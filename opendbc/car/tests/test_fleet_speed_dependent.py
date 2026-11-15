"""Fleet speed-dependent seed and safety gating regression."""
from types import SimpleNamespace
from opendbc.car.mazda.values import CAR as Mazda, MazdaFlags
from opendbc.car.gm.values import CAR as GM
from opendbc.sunnypilot.car.interfaces import get_speed_dep_config_for_car

def cp(car, brand, flags=0, min_speed=0.0):
  return SimpleNamespace(carFingerprint=car, brand=brand, flags=flags, minSteerSpeed=min_speed)

def test_cx9_donor_uses_cx9_measured_bins():
  donor = cp(Mazda.MAZDA_CX9, "mazda", MazdaFlags.STEER_TO_ZERO_EPS)
  bins = get_speed_dep_config_for_car(donor)
  assert bins["speed_bp"] == [6.5, 9.5, 12.0, 16.4, 21.0, 28.0, 35.0]
  assert bins["laf_bp"][0] == 2.67
  assert bins["seed_version"] == 1

def test_no_donor_eps_cannot_activate_donor_only_bins():
  stock = cp(Mazda.MAZDA_CX9, "mazda")
  assert get_speed_dep_config_for_car(stock) == {}

def test_suburban_has_independent_measured_bins():
  suburban = cp(GM.CHEVROLET_SUBURBAN_CAMERA_11TH_GEN, "gm")
  bins = get_speed_dep_config_for_car(suburban)
  assert bins["speed_bp"][0] == 6.5
  assert bins["laf_bp"][0] == 0.68
