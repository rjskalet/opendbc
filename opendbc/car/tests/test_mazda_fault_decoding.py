"""Mazda fault categorization and exact donor EPS DBC signal declarations."""
from pathlib import Path
import unittest

from opendbc.car.mazda.carstate import classify_mazda_steering_faults



class TestMazdaFaultDecoding(unittest.TestCase):
  def test_donor_eps_genuine_fault_is_permanent_even_if_camera_reports_no_error(self):
    temporary, permanent = classify_mazda_steering_faults(True, True, False, False, False, False)
    assert permanent and not temporary


  def test_donor_eps_camera_only_error_is_temporary_not_permanent(self):
    temporary, permanent = classify_mazda_steering_faults(True, False, True, True, False, False)
    assert temporary and not permanent


  def test_donor_eps_sustained_undelivered_request_is_temporary(self):
    temporary, permanent = classify_mazda_steering_faults(True, False, False, False, True, False)
    assert temporary and not permanent


  def test_donor_eps_expected_low_speed_block_is_not_a_fault(self):
    assert classify_mazda_steering_faults(True, False, False, False, False, True) == (False, False)


  def test_legacy_mazda_fault_behavior_is_retained(self):
    # The legacy permanent-fault signal remains CAM_LKAS.ERR_BIT_1 only.
    assert classify_mazda_steering_faults(False, False, True, True, False, False) == (False, True)
    assert classify_mazda_steering_faults(False, False, True, False, False, False) == (False, False)
    assert classify_mazda_steering_faults(False, False, False, False, False, True) == (True, False)


  def test_donor_eps_signal_layout_matches_documented_zoom_telemetry(self):
    dbc = (Path(__file__).resolve().parents[2] / "dbc" / "mazda_2017.dbc").read_text()
    assert 'SG_ LKAS_EFFECTIVE : 39|10@0+ (4,-2048) [-2048|2044]' in dbc
    assert 'SG_ LKAS_FAULT : 53|1@0+ (1,0) [0|1]' in dbc
