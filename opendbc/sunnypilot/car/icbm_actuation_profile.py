"""
Per-car actuation profile for Intelligent Cruise Button Management (ICBM).

On button-actuated (non-pcmCruiseSpeed) cars the stock ECU integrates the cruise buttons,
and every ECU does it differently. Cars without a measured profile retain the conservative
legacy tap-only behavior.
"""
from dataclasses import dataclass

from opendbc.car import structs

SendButtonState = structs.IntelligentCruiseButtonManagement.SendButtonState

TAP_EQUIVALENT = {
  SendButtonState.increaseHold: SendButtonState.increase,
  SendButtonState.decreaseHold: SendButtonState.decrease,
}


def tap_equivalent(send_button: SendButtonState) -> SendButtonState:
  return TAP_EQUIVALENT.get(send_button, send_button)


@dataclass(frozen=True)
class ICBMActuationProfile:
  tap_rate_hz: float = 5.
  longpress_step: int = 0
  longpress_first_step_s: float = 0.
  longpress_step_period_s: float = 0.
  longpress_metric_confirmed: bool = False
  decel_needs_stable_setpoint: bool = False

  @property
  def has_longpress(self) -> bool:
    return self.longpress_step > 0

  def supports_longpress(self, is_metric: bool) -> bool:
    return self.has_longpress and (self.longpress_metric_confirmed or not is_metric)


# Mazda measurements from ZoomPilot's stock-MRCC validation: reliable 5 Hz taps, physical
# long-press behavior on a 5 mph grid, and delayed deceleration until the dash setpoint settles.
ICBM_ACTUATION_PROFILES: dict[str, ICBMActuationProfile] = {
  'mazda': ICBMActuationProfile(
    tap_rate_hz=5.,
    longpress_step=5,
    longpress_first_step_s=0.6,
    longpress_step_period_s=0.55,
    longpress_metric_confirmed=False,
    decel_needs_stable_setpoint=True,
  ),
}

DEFAULT_PROFILE = ICBMActuationProfile()


def get_actuation_profile(brand: str) -> ICBMActuationProfile:
  return ICBM_ACTUATION_PROFILES.get(brand, DEFAULT_PROFILE)
