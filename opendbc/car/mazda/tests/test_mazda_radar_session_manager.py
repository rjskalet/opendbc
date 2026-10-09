"""
Radar UDS session-manager regression tests ported from current ZoomPilot.
These exercise only the shared Mazda-long session state machine, not newer lateral/TJA features.
"""

from opendbc.car import DT_CTRL
from opendbc.car.mazda.radar_session import RADAR_SESSION_LIMIT_FRAMES, RADAR_RESTORE_FRAMES, RadarSessionManager as _RadarSessionManager, RadarSessionState
from opendbc.car.mazda.values import CarControllerParams
from opendbc.sunnypilot.car.stock_ecu import StockEcuState


class RadarSessionManager(_RadarSessionManager):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.n = -1

  def update(self, *args, **kwargs):
    self.n += 1
    return super().update(*args, frame=self.n, **kwargs)


class TestRadarSessionBounds:
  def test_silencing_gives_up_bounded(self):
    m = RadarSessionManager()
    for _ in range(RADAR_SESSION_LIMIT_FRAMES + 2):
      state = m.update(True, True, False, standstill=True, session_refused=False, stock_radar_gone=False)
    assert state == RadarSessionState.HANDBACK and m.silencing_failed
    for _ in range(CarControllerParams.RADAR_UDS_STEP + RADAR_RESTORE_FRAMES):
      m.update(True, True, False, standstill=True, session_refused=False, stock_radar_gone=False)
    for _ in range(10):
      assert m.update(True, True, False, standstill=True, session_refused=False, stock_radar_gone=False) == RadarSessionState.STOCK

  def test_negative_response_gives_up_immediately(self):
    m = RadarSessionManager()
    m.update(True, True, False, standstill=True, session_refused=False, stock_radar_gone=False)
    assert m.state == RadarSessionState.SILENCING
    assert m.update(True, True, False, standstill=True, session_refused=True, stock_radar_gone=False) == RadarSessionState.HANDBACK
    assert m.silencing_failed

  def test_handback_stops_waiting_for_a_dead_radar(self):
    m = RadarSessionManager()
    m.update(True, False, False, standstill=True, session_refused=False, stock_radar_gone=True)
    assert m.state == RadarSessionState.SILENCED
    for _ in range(RADAR_SESSION_LIMIT_FRAMES + 2):
      state = m.update(True, False, True, standstill=True, session_refused=False, stock_radar_gone=True)
    assert state == RadarSessionState.HANDBACK
    assert m.handback_failed and not m.handback_completed
    assert m.diagnostic_message is None

  def test_ordered_handback_stays_stock_while_request_stands(self):
    m = RadarSessionManager()
    m.update(True, False, False, standstill=True, session_refused=False, stock_radar_gone=True)
    m.update(True, False, True, standstill=True, session_refused=False, stock_radar_gone=True)
    for _ in range(CarControllerParams.RADAR_UDS_STEP + RADAR_RESTORE_FRAMES):
      m.update(True, True, True, standstill=True, session_refused=False, stock_radar_gone=False)
    assert m.state == RadarSessionState.STOCK and m.handback_completed
    for alive in (True, False):
      for _ in range(5):
        assert m.update(True, alive, True, standstill=True, session_refused=False, stock_radar_gone=not alive) == RadarSessionState.STOCK
    assert m.status == StockEcuState.RESTORED

  def test_withdrawn_request_after_restore_is_fresh_start(self):
    m = RadarSessionManager()
    m.update(True, False, False, standstill=True, session_refused=False, stock_radar_gone=True)
    m.update(True, False, True, standstill=True, session_refused=False, stock_radar_gone=True)
    for _ in range(CarControllerParams.RADAR_UDS_STEP + RADAR_RESTORE_FRAMES):
      m.update(True, True, True, standstill=True, session_refused=False, stock_radar_gone=False)
    assert m.handback_completed
    assert m.update(True, True, False, standstill=True, session_refused=False, stock_radar_gone=False) == RadarSessionState.SILENCING
    assert not m.handback_completed

  def test_withdrawn_handback_finishes_restoration(self):
    m = RadarSessionManager()
    m.update(True, False, False, standstill=True, session_refused=False, stock_radar_gone=True)
    m.update(True, False, True, standstill=True, session_refused=False, stock_radar_gone=True)
    assert m.state == RadarSessionState.HANDBACK
    state = m.update(True, False, False, standstill=True, session_refused=False, stock_radar_gone=True)
    assert state == RadarSessionState.HANDBACK and not m.handback_completed

  def test_silencing_waits_for_standstill_but_adoption_does_not(self):
    m = RadarSessionManager()
    for _ in range(10):
      assert m.update(True, True, False, standstill=False, session_refused=False, stock_radar_gone=False) == RadarSessionState.STOCK
    assert m.update(True, True, False, standstill=True, session_refused=False, stock_radar_gone=False) == RadarSessionState.SILENCING

    m2 = RadarSessionManager()
    assert m2.update(True, False, False, standstill=False, session_refused=False, stock_radar_gone=True) == RadarSessionState.SILENCED

  def test_short_radar_gap_is_not_adopted(self):
    m = RadarSessionManager()
    for _ in range(int(CarControllerParams.STOCK_RADAR_GUARD_T / DT_CTRL)):
      assert m.update(True, False, False, standstill=False, session_refused=False, stock_radar_gone=False) == RadarSessionState.STOCK
    assert m.update(True, False, False, standstill=False, session_refused=False, stock_radar_gone=True) == RadarSessionState.SILENCED

  def test_returned_radar_is_resilenced_only_under_teardown_gate(self):
    m = RadarSessionManager()
    m.update(True, False, False, standstill=False, session_refused=False, stock_radar_gone=True)
    assert m.state == RadarSessionState.SILENCED
    assert m.update(True, True, False, standstill=False, session_refused=False, stock_radar_gone=False) == RadarSessionState.STOCK
    for _ in range(300):
      assert m.update(True, True, False, standstill=False, session_refused=False, stock_radar_gone=False) == RadarSessionState.STOCK
    assert m.update(True, True, False, standstill=True, session_refused=False, stock_radar_gone=False) == RadarSessionState.SILENCING
