#!/usr/bin/env python3
from opendbc.car import Bus, get_safety_config, structs
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.interfaces import CarInterfaceBase
from opendbc.car.mazda.carcontroller import CarController
from opendbc.car.mazda.carstate import CarState
from opendbc.car.mazda.radar_interface import RadarInterface
from opendbc.car.mazda.values import CAR, DBC, G46L_RADAR_FW, LKAS_LIMITS, STEER_TO_ZERO_EPS_FW, CarControllerParams, MazdaFlags, MazdaSafetyFlags


class CarInterface(CarInterfaceBase):
  CarState = CarState
  CarController = CarController
  RadarInterface = RadarInterface

  @staticmethod
  def _get_params(ret: structs.CarParams, candidate, fingerprint, car_fw, alpha_long, is_release, docs) -> structs.CarParams:
    ret.brand = "mazda"
    ret.safetyConfigs = [get_safety_config(structs.CarParams.SafetyModel.mazda)]

    # ZoomPilot alpha-long supports the normal Mazda radar-track dialect and the older G46L
    # dialect (vision lead fallback). Keep eligibility firmware-gated rather than broadening it.
    g46l_radar = any(fw.ecu == structs.CarParams.Ecu.fwdRadar and fw.fwVersion.rstrip(b'\x00') in G46L_RADAR_FW for fw in car_fw)
    if g46l_radar:
      ret.flags |= MazdaFlags.G46L_RADAR.value
    ret.radarUnavailable = Bus.radar not in DBC[candidate] or g46l_radar

    # The donor 2022 CX-5 EPS carries its steering capability with it. Detect from firmware so
    # an older CX-9 body with a verified donor rack gets the same lateral path as ZoomPilot.
    eps_fw = {fw.fwVersion for fw in car_fw if fw.ecu == structs.CarParams.Ecu.eps}
    steer_to_zero = not eps_fw.isdisjoint(STEER_TO_ZERO_EPS_FW)
    if steer_to_zero:
      ret.flags |= MazdaFlags.STEER_TO_ZERO_EPS.value
      ret.safetyConfigs[0].safetyParam |= MazdaSafetyFlags.STEER_TO_ZERO_EPS.value

    # Alpha long is offered only on the steer-to-zero EPS and a radar dialect ZoomPilot has
    # validated. The toggle remains AlphaLongitudinalEnabled, so stock MRCC is the default.
    ret.alphaLongitudinalAvailable = steer_to_zero and (Bus.radar in DBC[candidate] or g46l_radar)
    ret.openpilotLongitudinalControl = alpha_long and ret.alphaLongitudinalAvailable
    if ret.openpilotLongitudinalControl:
      ret.safetyConfigs[0].safetyParam |= MazdaSafetyFlags.LONG.value
      ret.pcmCruise = True
      ret.radarUnavailable = True
      ret.stopAccel = -1.024
      ret.longitudinalActuatorDelay = 0.36

    # Preserve upstream-supported bodies, and additionally lift dashcam-only when the capable EPS
    # is actually detected. Do not broadly enable unsupported older Mazda EPS firmware.
    ret.dashcamOnly = candidate not in (CAR.MAZDA_CX5_2022, CAR.MAZDA_CX9_2021) and not steer_to_zero

    ret.steerActuatorDelay = 0.14 if steer_to_zero else 0.1
    ret.steerLimitTimer = 0.8

    CarInterfaceBase.configure_torque_tune(candidate, ret.lateralTuning)
    if steer_to_zero and ret.lateralTuning.which() == 'torque':
      # params.toml is expressed on upstream Mazda's 800-count normalization. Convert once
      # into the donor EPS's flat 1200-count scale while preserving counts on the wire.
      tune_scale = CarControllerParams.EPS_STEER_MAX / CarControllerParams.TUNE_STEER_MAX
      ret.lateralTuning.torque.latAccelFactor *= tune_scale
      ret.lateralTuning.torque.friction /= tune_scale

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
