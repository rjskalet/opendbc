"""
Advertised-lead state-machine regression tests ported from current ZoomPilot.
"""

import pytest

from opendbc.car import DT_CTRL
from opendbc.car.mazda.longitudinal import LEAD_DEBOUNCE_FRAMES, AdvertisedLead


def drive(al, n, **kwargs):
  defaults = dict(lead_visible=True, d_rel=40.0, v_rel=0.0, holding=False)
  defaults.update(kwargs)
  for _ in range(n):
    al.update(**defaults)
  return al


class TestAdvertisedLead:
  def test_lead_follows_only_a_steady_state(self):
    al = AdvertisedLead()
    drive(al, LEAD_DEBOUNCE_FRAMES - 1)
    assert not al.has_lead and al.ctrl_phase == 0
    drive(al, 1)
    assert al.has_lead and al.lead == (40.0, 0.0) and al.ctrl_phase == 2

    drive(al, LEAD_DEBOUNCE_FRAMES - 1, lead_visible=False, d_rel=0.)
    assert al.has_lead
    drive(al, 1, lead_visible=False, d_rel=0.)
    assert not al.has_lead and al.ctrl_phase == 0

  def test_lead_flicker_never_reaches_the_bus_state(self):
    al = AdvertisedLead()
    for n, visible in ((15, True), (5, False), (7, True), (13, False), (10, True)):
      drive(al, n, lead_visible=visible)
      assert not al.has_lead

  def test_measurement_is_coasted_across_a_dropout(self):
    al = AdvertisedLead()
    drive(al, 2 * LEAD_DEBOUNCE_FRAMES, d_rel=120.0, v_rel=0.5)
    assert al.lead == (120.0, 0.5)
    coast_frames = LEAD_DEBOUNCE_FRAMES - 1
    drive(al, coast_frames, lead_visible=False, d_rel=0., v_rel=0.)
    assert al.lead is not None
    d, v = al.lead
    assert v == 0.5
    assert d == pytest.approx(120.0 + 0.5 * coast_frames * DT_CTRL, abs=1e-6)

  def test_holding_reports_stop_phase_only_with_a_lead(self):
    al = AdvertisedLead()
    drive(al, 2 * LEAD_DEBOUNCE_FRAMES, holding=True)
    assert al.ctrl_phase == 3
    drive(al, 2 * LEAD_DEBOUNCE_FRAMES, lead_visible=False, d_rel=0., holding=True)
    assert not al.has_lead and al.ctrl_phase == 0
