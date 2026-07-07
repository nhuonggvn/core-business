import unittest
from datetime import datetime, timezone
from src.event_handlers import handle_access_event, access_denied_counter, recent_events

class TestBruteforceLogic(unittest.TestCase):
    def setUp(self):
        # Reset trạng thái trước mỗi bài test
        access_denied_counter.clear()
        recent_events.clear()

    def build_access_event(self, uid: str, result: str, location: str = "Gate 1") -> dict:
        return {
            "event_id": "EVT-123",
            "uid": uid,
            "access_result": result,
            "location": location,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def test_access_denied_increases_counter(self):
        event = self.build_access_event("USER-01", "denied")
        alert = handle_access_event(event)
        
        self.assertIsNone(alert)
        self.assertEqual(access_denied_counter["USER-01"], 1)
        
        alert2 = handle_access_event(event)
        self.assertIsNone(alert2)
        self.assertEqual(access_denied_counter["USER-01"], 2)

    def test_access_bruteforce_alert_triggered(self):
        event = self.build_access_event("USER-02", "denied")
        
        handle_access_event(event)
        handle_access_event(event)
        
        alert = handle_access_event(event)
        self.assertIsNotNone(alert)
        self.assertEqual(alert["alert_type"], "access_bruteforce")
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["origin_event_id"], "EVT-123")
        self.assertIn("USER-02", alert["message"])

    def test_access_granted_resets_counter(self):
        event_denied = self.build_access_event("USER-03", "denied")
        event_granted = self.build_access_event("USER-03", "granted")
        
        handle_access_event(event_denied)
        handle_access_event(event_denied)
        self.assertEqual(access_denied_counter["USER-03"], 2)
        
        alert = handle_access_event(event_granted)
        self.assertIsNone(alert)
        self.assertEqual(access_denied_counter["USER-03"], 0)

if __name__ == '__main__':
    unittest.main()
