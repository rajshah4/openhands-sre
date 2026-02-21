from __future__ import annotations

import time
import unittest

from web_demo.app import app, manager


class WebDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()
        manager.stop()

    def test_state_endpoint(self) -> None:
        resp = self.client.get('/api/state')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn('status', body)
        self.assertIn('summary', body)

    def test_run_lifecycle_simulation(self) -> None:
        payload = {
            'simulate': True,
            'mode': 'optimized',
            'optimizer': 'gepa',
            'incidents': 8,
            'concurrency': 2,
            'simulate_latency_ms': 20,
        }

        start = self.client.post('/api/run', json=payload)
        self.assertEqual(start.status_code, 200)
        start_json = start.get_json()
        self.assertTrue(start_json['ok'])

        deadline = time.time() + 8
        state = None
        while time.time() < deadline:
            resp = self.client.get('/api/state')
            self.assertEqual(resp.status_code, 200)
            state = resp.get_json()
            if state['status'] in {'completed', 'failed', 'cancelled'}:
                break
            time.sleep(0.05)

        self.assertIsNotNone(state)
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['summary']['total'], 8)
        self.assertEqual(state['summary']['completed'], 8)


if __name__ == '__main__':
    unittest.main()
