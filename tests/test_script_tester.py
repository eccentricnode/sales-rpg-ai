import unittest
import json
from unittest.mock import MagicMock, patch
from validation.script_tester import ScriptTester

import os

class TestScriptTester(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_script_tester.db"
        self.tester = ScriptTester(db_path=self.db_path)
        # Mock the analyzer to avoid real API calls
        self.tester.analyzer = MagicMock()
        self.tester.analyzer.model = "test-model"

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_load_script(self):
        self.assertIn("KubeCraft", self.tester.script_content)

    def test_construct_system_prompt(self):
        prompt = self.tester._construct_system_prompt()
        self.assertIn("SALES SCRIPT:", prompt)
        self.assertIn("OUTPUT FORMAT (JSON ONLY):", prompt)

    def test_test_with_snippet(self):
        # Mock response
        mock_response = json.dumps({
            "stage": "Opening",
            "tie_downs": [],
            "flags": [],
            "suggestion": "Say hello"
        })
        self.tester.analyzer.analyze.return_value = mock_response
        
        result = self.tester.test_with_snippet("Hello there")
        self.assertEqual(result["stage"], "Opening")
        self.tester.analyzer.analyze.assert_called_once()

    def test_full_workflow(self):
        # 1. Save Call
        call_id = self.tester.save_call("Test Call", "Transcript content")
        self.assertIsNotNone(call_id)
        
        # 2. Run Analysis
        mock_response = json.dumps({
            "stage": "Discovery",
            "tie_downs": ["Right?"],
            "flags": [],
            "suggestion": "Ask about budget"
        })
        self.tester.analyzer.analyze.return_value = mock_response
        
        run_id = self.tester.run_analysis(call_id)
        self.assertIsNotNone(run_id)
        
        # 3. Get Results
        results = self.tester.get_results()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].call_name, "Test Call")
        self.assertTrue(results[0].passed)
        self.assertIn("Discovery", results[0].notes)

if __name__ == '__main__':
    unittest.main()
