import math
import unittest

from opendbc.car import DT_CTRL, CanData, structs
from opendbc.car.car_helpers import interfaces
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.fingerprints import FW_VERSIONS
from opendbc.car.fw_versions import FW_QUERY_CONFIGS
from opendbc.car.interfaces import CarInterfaceBase, get_interface_attr
from opendbc.car.mazda.values import CAR as MAZDA, STEER_TO_ZERO_EPS_FW, CarControllerParams as MazdaControllerParams
from opendbc.car.mazda.values import MazdaFlags, MazdaSafetyFlags
from opendbc.car.values import PLATFORMS
from opendbc.testing import Fuzzy, fuzzy_test, parameterized

ALL_ECUS = tuple(sorted({ecu for ecus in FW_VERSIONS.values() for ecu in ecus} |
                        {ecu for config in FW_QUERY_CONFIGS.values() for ecu in config.extra_ecus}))

ALL_REQUESTS = tuple(sorted({tuple(r.request) for config in FW_QUERY_CONFIGS.values() for r in config.requests}))

# From panda/python/__init__.py
DLC_TO_LEN = (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64)


def get_fuzzy_car_interface(car_name: str, fuzzy: Fuzzy) -> CarInterfaceBase:
  fingerprint = dict(fuzzy.list(lambda: (fuzzy.integer(0, 0x800), fuzzy.choice(DLC_TO_LEN))))
  # reduce search space by duplicating CAN fingerprints across all buses
  fingerprints = dict.fromkeys(range(7), fingerprint)

  def generate_car_fw():
    ecu, address, sub_address = fuzzy.choice(ALL_ECUS)
    return structs.CarParams.CarFw(ecu=ecu, address=address, subAddress=sub_address or 0,
                                  request=fuzzy.choice(ALL_REQUESTS))

  # initialize car interface
  CarInterface = interfaces[car_name]
  car_fw = fuzzy.list(generate_car_fw)
  alpha_long = fuzzy.choice([True, False])
  car_params = CarInterface.get_params(car_name, fingerprints, car_fw,
                                       alpha_long=alpha_long, is_release=False, docs=False)
  car_params_sp = CarInterface.get_params_sp(car_params, car_name, fingerprints, car_fw,
                                             alpha_long=alpha_long, is_release_sp=False, docs=False)
  return CarInterface(car_params, car_params_sp)


def _make_car_test(car_name):
  @fuzzy_test(max_examples=15)
  def test(self, fuzzy):
    car_interface = get_fuzzy_car_interface(car_name, fuzzy)
    car_params = car_interface.CP.as_reader()
    car_params_sp = car_interface.CP_SP

    assert car_params.mass > 1
    assert car_params.wheelbase > 0
    # centerToFront is center of gravity to front wheels, assert a reasonable range
    assert car_params.wheelbase * 0.3 < car_params.centerToFront < car_params.wheelbase * 0.7
    assert car_params.maxLateralAccel > 0

    # Longitudinal sanity checks
    assert len(car_params.longitudinalTuning.kiV) == len(car_params.longitudinalTuning.kiBP)

    # If we're using the interceptor for gasPressed, we should be commanding gas with it
    if car_params_sp.enableGasInterceptor:
      assert car_params.openpilotLongitudinalControl

    # Lateral sanity checks
    if car_params.steerControlType not in (structs.CarParams.SteerControlType.angle, structs.CarParams.SteerControlType.curvature):
      tune = car_params.lateralTuning
      if tune.which() == 'pid':
        assert not math.isnan(tune.pid.kf) and tune.pid.kf >= 0
        assert len(tune.pid.kpV) > 0 and len(tune.pid.kpV) == len(tune.pid.kpBP)
        assert len(tune.pid.kiV) > 0 and len(tune.pid.kiV) == len(tune.pid.kiBP)

      elif tune.which() == 'torque':
        assert not math.isnan(tune.torque.latAccelFactor) and tune.torque.latAccelFactor > 0
        assert not math.isnan(tune.torque.friction) and tune.torque.friction > 0

    # Run car interface
    # TODO: generate random messages
    now_nanos = 0
    CC = structs.CarControl().as_reader()
    CC_SP = structs.CarControlSP()
    for _ in range(10):
      car_interface.update([])
      car_interface.apply(CC, CC_SP, now_nanos)
      now_nanos += DT_CTRL * 1e9  # 10 ms

    CC = structs.CarControl()
    CC.enabled = True
    CC.latActive = True
    CC.longActive = True
    CC = CC.as_reader()
    for _ in range(10):
      car_interface.update([])
      car_interface.apply(CC, CC_SP, now_nanos)
      now_nanos += DT_CTRL * 1e9  # 10ms

    # Test radar interface
    radar_interface = car_interface.RadarInterface(car_params, car_params_sp)
    assert radar_interface

    # Run radar interface once
    radar_interface.update([])
    if not car_params.radarUnavailable and radar_interface.rcp is not None and \
       hasattr(radar_interface, '_update') and hasattr(radar_interface, 'trigger_msg'):
      radar_interface._update([radar_interface.trigger_msg])

    # Test radar fault
    if not car_params.radarUnavailable and radar_interface.rcp is not None:
      cans = [(0, [CanData(0, b'', 0) for _ in range(5)])]
      rr = radar_interface.update(cans)
      assert rr is None or len(rr.errors) > 0

  return test


class TestCarInterfaces(unittest.TestCase):
  def test_interface_attrs(self):
    """Asserts basic behavior of interface attribute getter"""
    num_brands = len(get_interface_attr('CAR'))
    assert num_brands >= 12

    # Should return value for all brands when not combining, even if attribute doesn't exist
    ret = get_interface_attr('FAKE_ATTR')
    assert len(ret) == num_brands

    # Make sure we can combine dicts
    ret = get_interface_attr('DBC', combine_brands=True)
    assert len(ret) >= 160

    # We don't support combining non-dicts
    ret = get_interface_attr('CAR', combine_brands=True)
    assert len(ret) == 0

    # If brand has None value, it shouldn't return when ignore_none=True is specified
    none_brands = {b for b, v in get_interface_attr('FINGERPRINTS').items() if v is None}
    assert len(none_brands) >= 1

    ret = get_interface_attr('FINGERPRINTS', ignore_none=True)
    none_brands_in_ret = none_brands.intersection(ret)
    assert len(none_brands_in_ret) == 0, f'Brands with None values in ignore_none=True result: {none_brands_in_ret}'


class TestMazdaDonorEpsParams(unittest.TestCase):
  @staticmethod
  def get_params(fw_version: bytes):
    car_fw = [structs.CarParams.CarFw(ecu="eps", fwVersion=fw_version)]
    return interfaces[MAZDA.MAZDA_CX9].get_params(
      MAZDA.MAZDA_CX9, {i: {} for i in range(8)}, car_fw, False, False, False,
    )

  @parameterized("fw_version", sorted(STEER_TO_ZERO_EPS_FW))
  def test_recognized_eps_firmware_enables_donor_capability(self, fw_version):
    CP = self.get_params(fw_version)

    self.assertEqual(CP.carFingerprint, MAZDA.MAZDA_CX9)
    self.assertTrue(CP.flags & MazdaFlags.STEER_TO_ZERO_EPS)
    self.assertTrue(CP.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS)
    self.assertEqual(CP.minSteerSpeed, 0.0)
    self.assertAlmostEqual(CP.steerActuatorDelay, 0.14)
    self.assertFalse(CP.dashcamOnly)

  def test_unrecognized_eps_firmware_keeps_legacy_capability(self):
    CP = self.get_params(b'UNKNOWN-3210X-A-00\x00\x00\x00\x00\x00\x00\x00')

    self.assertEqual(CP.carFingerprint, MAZDA.MAZDA_CX9)
    self.assertFalse(CP.flags & MazdaFlags.STEER_TO_ZERO_EPS)
    self.assertFalse(CP.safetyConfigs[0].safetyParam & MazdaSafetyFlags.STEER_TO_ZERO_EPS)
    self.assertEqual(CP.minSteerSpeed, 45 * CV.KPH_TO_MS)
    self.assertAlmostEqual(CP.steerActuatorDelay, 0.1)
    self.assertTrue(CP.dashcamOnly)

  def test_donor_controller_limits(self):
    params = MazdaControllerParams(self.get_params(next(iter(STEER_TO_ZERO_EPS_FW))))

    self.assertEqual(params.STEER_MAX, 1200)
    self.assertEqual(params.STEER_DELTA_UP, 12)
    self.assertEqual(params.STEER_DELTA_DOWN, 12)
    self.assertEqual(params.STEER_DRIVER_MULTIPLIER, 15)
    self.assertEqual(params.STEER_DRIVER_ALLOWANCE, 15)
    self.assertFalse(hasattr(params, "STEER_MAX_LOOKUP"))
    self.assertEqual(params.EPS_CEILING_LOOKUP, (
      [8.0, 8.5, 9.4, 10.3, 11.2, 12.1, 13.0, 13.9, 14.5],
      [1148, 1132, 1092, 1048, 1012, 920, 808, 676, 620],
    ))


for car_name in sorted(PLATFORMS):
  setattr(TestCarInterfaces, f'test_car_interfaces_{car_name}', _make_car_test(car_name))
