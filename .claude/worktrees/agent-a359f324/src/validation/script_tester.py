import os
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from openai import OpenAI
from validation.db import ValidationDB
from realtime.models import ConversationState

# Configuration
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "../../knowledge_base/kubecraft_script.md")
DEFAULT_MODEL = "phi-3.5-mini"
DEFAULT_BASE_URL = "http://localhost:8081/v1"

@dataclass
class AnalysisResult:
    call_id: Optional[str]
    call_name: str
    passed: bool
    notes: str
    raw_output: Dict[str, Any]

class ScriptTester:
    def __init__(self, db_path: str = "validation.db", base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL):
        self.db = ValidationDB(db_path)
        self.client = OpenAI(base_url=base_url, api_key="dummy")
        self.model = model
        self.script_content = self._load_script()
        
    def _load_script(self) -> str:
        """Load the sales script from the knowledge base."""
        try:
            with open(SCRIPT_PATH, "r") as f:
                return f.read()
        except FileNotFoundError:
            return "Error: Script file not found."

    def _construct_system_prompt(self) -> str:
        """Create the system prompt with the script injected."""
        return f"""You are a Sales AI Assistant. Your goal is to analyze sales calls against a specific script.
        
        SALES SCRIPT:
        {self.script_content}
        
        INSTRUCTIONS:
        1. Analyze the provided transcript snippet.
        2. Identify the current stage of the call based on the script.
        3. Detect any "Tie-Downs" (questions confirming agreement, e.g., "Does that make sense?").
        4. Flag any missed steps or warnings (e.g., pitching before qualifying).
        5. Suggest the next best response from the script.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "stage": "Script Section Name",
            "tie_downs": ["list", "of", "detected", "tie-downs"],
            "flags": ["list", "of", "warnings"],
            "suggestion": "Verbatim suggestion from script",
            "reasoning": "Why this suggestion?"
        }}
        """

    def _call_llm(self, text: str, system_prompt: str) -> str:
        """Helper to call the LLM with specific parameters."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=1000,
            temperature=0.1,
            stop=["<|end|>", "<|end_of_text|>", "\n\n"]
        )
        return response.choices[0].message.content

    def _clean_response(self, response: str) -> str:
        """Strip markdown code blocks from response."""
        if "```json" in response:
            response = response.split("```json")[1]
        if "```" in response:
            response = response.split("```")[0]
        return response.strip()

    def test_with_snippet(self, text: str) -> Dict[str, Any]:
        """
        Mode 1: Development Testing
        Quickly test a snippet without saving to DB.
        """
        system_prompt = self._construct_system_prompt()
        
        try:
            response_str = self._call_llm(text, system_prompt)
            response_str = self._clean_response(response_str)
            
            # Parse JSON
            try:
                return json.loads(response_str)
            except json.JSONDecodeError:
                return {"error": "Failed to parse JSON", "raw": response_str}
                
        except Exception as e:
            return {"error": str(e)}

    def save_call(self, name: str, transcript: str, duration: int = 0) -> str:
        """
        Mode 2: Live Call Storage
        Save a call to the database.
        """
        return self.db.add_call(name, transcript, duration)

    def run_analysis(self, call_id: str) -> str:
        """
        Process a saved call and store the result.
        Returns the test_run_id.
        """
        call = self.db.get_call(call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found")
            
        transcript = call['transcript']
        system_prompt = self._construct_system_prompt()
        
        response_str = self._call_llm(transcript, system_prompt)
        response_str = self._clean_response(response_str)
        
        # Log the run
        # We don't have an 'expected_id' yet for live calls, so we might pass None or create a dummy one.
        # The schema requires expected_id? Let's check db.py.
        # db.py: expected_id TEXT REFERENCES expected_outputs(id)
        # It seems mandatory in the schema. 
        # For live calls, we might not have ground truth yet.
        # We should probably make expected_id optional in the DB or create a placeholder.
        # For now, I'll create a placeholder expected output for this call if one doesn't exist.
        
        # Create a dummy expected output to satisfy FK
        exp_id = self.db.add_expected_output(
            call_id=call_id,
            tie_downs=[],
            script_pos="unknown",
            flags=[],
            suggestion="unknown",
            notes="Auto-generated placeholder for live call"
        )
        
        run_id = self.db.log_test_run(
            call_id=call_id,
            expected_id=exp_id,
            model=self.model,
            script_ver="v1.0",
            raw_output=response_str
        )
        
        return run_id

    def get_results(self, date_str: Optional[str] = None) -> List[AnalysisResult]:
        """
        Retrieve results for review.
        date_str format: YYYY-MM-DD
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT tr.id, c.id as call_id, c.name, tr.raw_output, tr.created_at
            FROM test_runs tr
            JOIN calls c ON tr.call_id = c.id
        """
        params = []
        
        if date_str:
            query += " WHERE date(tr.created_at) = ?"
            params.append(date_str)
            
        query += " ORDER BY tr.created_at DESC"
        
        rows = cursor.execute(query, params).fetchall()
        conn.close()
        
        results = []
        for row in rows:
            try:
                parsed = json.loads(row['raw_output'])
                # Simple heuristic for "passed" - valid JSON and has stage
                passed = "stage" in parsed
                notes = f"Stage: {parsed.get('stage', 'Unknown')}"
            except:
                parsed = {"raw": row['raw_output']}
                passed = False
                notes = "Failed to parse JSON"
                
            results.append(AnalysisResult(
                call_id=row['call_id'],
                call_name=row['name'],
                passed=passed,
                notes=notes,
                raw_output=parsed
            ))
            
        return results

    def test_script_only(self, text: str) -> Dict[str, Any]:
        """
        Minimal test mode: Script + Simple Instructions only.
        No complex logic, just script matching.
        """
        system_prompt = f"""You are a Sales Assistant.
        
        SALES SCRIPT:
        {self.script_content}
        
        INSTRUCTIONS:
        1. Read the transcript snippet.
        2. Determine where we are in the script.
        3. Identify key information mentioned by the prospect.
        4. Suggest the next response based strictly on the script.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "script_location": "Section Name",
            "key_points": ["point 1", "point 2"],
            "suggestion": "Verbatim response from script"
        }}
        """
        
        try:
            response_str = self._call_llm(text, system_prompt)
            response_str = self._clean_response(response_str)
            
            try:
                return json.loads(response_str)
            except json.JSONDecodeError:
                return {"error": "Failed to parse JSON", "raw": response_str}
                
        except Exception as e:
            return {"error": str(e)}

# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sales Script Tester")
    subparsers = parser.add_subparsers(dest="command")
    
    # Snippet Command
    snippet_parser = subparsers.add_parser("snippet", help="Test a text snippet")
    snippet_parser.add_argument("text", help="Text to analyze")

    # Minimal Command
    minimal_parser = subparsers.add_parser("minimal", help="Test snippet with minimal script-only prompt")
    minimal_parser.add_argument("text", help="Text to analyze")
    
    # Save Call Command
    save_parser = subparsers.add_parser("save", help="Save a live call")
    save_parser.add_argument("--name", required=True, help="Call name")
    save_parser.add_argument("--file", required=True, help="Path to transcript file")
    
    # Analyze Command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a saved call")
    analyze_parser.add_argument("call_id", help="UUID of the call")
    
    # Review Command
    review_parser = subparsers.add_parser("review", help="Review results")
    review_parser.add_argument("--date", help="YYYY-MM-DD")
    
    args = parser.parse_args()
    tester = ScriptTester()
    
    if args.command == "snippet":
        print(json.dumps(tester.test_with_snippet(args.text), indent=2))

    elif args.command == "minimal":
        print(json.dumps(tester.test_script_only(args.text), indent=2))
        
    elif args.command == "save":
        with open(args.file, 'r') as f:
            transcript = f.read()
        call_id = tester.save_call(args.name, transcript)
        print(f"Saved Call ID: {call_id}")
        
    elif args.command == "analyze":
        run_id = tester.run_analysis(args.call_id)
        print(f"Analysis Run ID: {run_id}")
        
    elif args.command == "review":
        results = tester.get_results(args.date)
        for r in results:
            status = "✅" if r.passed else "❌"
            print(f"{status} {r.call_name} ({r.call_id[:8]}...): {r.notes}")
