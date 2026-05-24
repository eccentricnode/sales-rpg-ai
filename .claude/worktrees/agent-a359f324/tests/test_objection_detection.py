#!/usr/bin/env python3
"""
Test objection detection with mock sales transcript.
"""

import sys
import os
from pathlib import Path

# Load .env file
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Import the analysis function
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from transcribe_and_analyze import analyze_objections, print_results

# Mock sales call with clear objections
mock_transcript = """
Salesperson: So this package is $997 per month for the premium plan.

Customer: Wow, that's really expensive. I wasn't expecting it to be that much.

Salesperson: I understand. What were you expecting the investment to be?

Customer: I don't know, maybe like $500? I need to think about this.

Salesperson: Of course, take your time. What specific concerns do you have?

Customer: Well, the price is one thing. And honestly, I'd need to talk to my wife about this before making any decision. She handles most of our financial decisions.

Salesperson: That makes total sense. When do you think you could discuss it with her?

Customer: Probably this weekend. But I'm just not sure if now is the right time for us. Maybe we should wait a few months.
"""

print("\n" + "="*60)
print("TESTING OBJECTION DETECTION")
print("="*60)
print("\nMock Sales Transcript:")
print("-"*60)
print(mock_transcript)
print("-"*60 + "\n")

# Analyze for objections
results = analyze_objections(mock_transcript)

# Print results
print_results(results)
