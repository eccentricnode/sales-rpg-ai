import os
import sys
import unittest
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from validation.db import ValidationDB

class TestValidationDB(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_validation.db"
        self.db = ValidationDB(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_full_flow(self):
        # 1. Add Call
        call_id = self.db.add_call(
            name="Test Call 1",
            transcript="Hello, is this the decision maker?",
            duration=120
        )
        self.assertIsNotNone(call_id)
        
        # Verify Call
        call = self.db.get_call(call_id)
        self.assertEqual(call['name'], "Test Call 1")

        # 2. Add Expected Output
        exp_id = self.db.add_expected_output(
            call_id=call_id,
            tie_downs=["decision maker"],
            script_pos="opening",
            flags=["check_authority"],
            suggestion="Ask for title"
        )
        self.assertIsNotNone(exp_id)

        # 3. Log Test Run
        run_id = self.db.log_test_run(
            call_id=call_id,
            expected_id=exp_id,
            model="phi-3.5",
            script_ver="v1.0",
            raw_output='{"analysis": "opening"}'
        )
        self.assertIsNotNone(run_id)

        # 4. Log Result
        res_id = self.db.log_result(
            run_id=run_id,
            caught_ties=True,
            correct_pos=True,
            correct_flags=True,
            good_sugg=True,
            passed=True,
            notes="Perfect run"
        )
        self.assertIsNotNone(res_id)
        
        print("✅ Validation DB CRUD Test Passed")

if __name__ == '__main__':
    unittest.main()
