#!/usr/bin/env python3
from opendbc.car import get_safety_config, structs
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.interfaces import CarInterfaceBase
from opendbc.car.mazda.carcontroller import CarController
from opendbc.car.mazda.carstate import CarState
from opendbc.car.mazda.values import CAR, LKAS_LIMITS, STEER_TO_ZERO_EPS_FW, TORQUE_TUNES, CarControllerParams, MazdaFlags, MazdaSafetyFlags


class CarInterface(CarInterfaceBase):
  CarState = CarState
  CarController = CarController

  @staticmethod
  def configure_torque_tune(candidate, tune, steering_angle_deadzone_deg=0.0):
    # Populate the upstream 800-count Mazda tune first. The EPS-specific scale is applied
    # separately once CarParams has identified the physical EPS firmware.
    CarInterfaceBase.configure_torque_tune(candidate, tune, steering_angle_deadzone_deg)
    lat_accel_factor, friction = TORQUE_TUNES.get(candidate, (tune.torque.latAccelFactor, tune.torque.friction))
    tune.torque.latAccelFactor = lat_accel_factor
    tune.torque.friction = friction

  @staticmethod
  def apply_torque_tune_scale(tune, scale: float):
    if scale == 1.0:
      return
    tune.torque.latAccelFactor *= scale
    tune.torque.friction /= scale

  @staticmethod
  def _get_params(ret: structs.CarParams, candidate, fingerprint, car_fw, alpha_long, is_release, docs) -> structs.CarParams:
    ret.brand = "mazda"
    ret.safetyConfigs = [get_safety_config(structs.CarParams.SafetyModel.mazda)]
    ret.radarUnavailable = True

    # The donor 2022 CX-5 EPS carries its steering capability with it. Detect from firmware so
    # an older CX-9 body with a verified donor rack gets the same lateral path as ZoomPilot.
    eps_fw = {fw.fwVersion for fw in car_fw if fw.ecu == 'eps'}
    steer_to_zero = not eps_fw.isdisjoint(STEER_TO_ZERO_EPS_FW)
    if steer_to_zero:
      ret.flags |= MazdaFlags.STEER_TO_ZERO_EPS.value
      ret.safetyConfigs[0].safetyParam |= MazdaSafetyFlags.STEER_TO_ZERO_EPS.value

    # Preserve upstream-supported bodies, and additionally lift dashcam-only when the capable EPS
    # is actually detected. Do not broadly enable unsupported older Mazda EPS firmware.
    ret.dashcamOnly = candidate not in (CAR.MAZDA_CX5_2022, CAR.MAZDA_CX9_2021) and not steer_to_zero

    ret.steerActuatorDelay = 0.14 if steer_to_zero else 0.1
    ret.steerLimitTimer = 0.8

    CarInterface.configure_torque_tune(candidate, ret.lateralTuning)
    CarInterface.apply_torque_tune_scale(ret.lateralTuning, CarControllerParams(ret).TUNE_SCALE)

    if not steer_to_zero and candidate not in (CAR.MAZDA_CX5_2022,):
      ret.minSteerSpeed = LKAS_LIMITS.DISABLE_SPEED * CV.KPH_TO_MS
    else:
      ret.minSteerSpeed = 0.0

    ret.centerToFront = ret.wheelbase * 0.41

    return ret

  @staticmethod
  def _get_params_sp(stock_cp: structs.CarParams, ret: structs.CarParamsSP, candidate, fingerprint: dict[int, dict[int, int]],
                     car_fw: list[structs.CarParams.CarFw], alpha_long: bool, is_release_sp: bool, docs: bool) -> structs.CarParamsSP:
    ret.intelligentCruiseButtonManagementAvailable = True

    return ret
