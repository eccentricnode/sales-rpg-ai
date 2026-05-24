import unittest
from unittest.mock import MagicMock, patch
import time
from src.realtime.buffer_manager import DualBufferManager, BufferConfig, Segment

class TestDualBufferManager(unittest.TestCase):
    def setUp(self):
        self.mock_callback = MagicMock()
        self.config = BufferConfig(
            time_threshold_seconds=15.0,
            min_completed_segments=10,
            min_characters=500,
            sentence_end_triggers=False,
            silence_threshold_seconds=2.0
        )
        self.manager = DualBufferManager(self.config, self.mock_callback)

    def create_segment(self, text, start, end, completed=True):
        return {
            "text": text,
            "start": start,
            "end": end,
            "completed": completed
        }

    def test_no_trigger_on_small_input(self):
        """Ensure analysis is NOT triggered for small, quick inputs."""
        segments = [self.create_segment("Hello world.", 0.0, 1.0)]
        
        # Mock time to be just after start
        with patch('time.time', return_value=1000.0):
            self.manager.last_analysis_time = 1000.0
            self.manager.on_transcript_chunk("Hello world.", segments)
            
        self.mock_callback.assert_not_called()

    def test_trigger_on_time_threshold(self):
        """Ensure analysis IS triggered after time threshold elapses."""
        segments = [self.create_segment("This is a long enough sentence to be interesting.", 0.0, 5.0)]
        
        # 1. Initial input (Time 1000)
        with patch('time.time', return_value=1000.0):
            self.manager.last_analysis_time = 1000.0
            self.manager.on_transcript_chunk("Input 1", segments)
        self.mock_callback.assert_not_called()

        # 2. Later input (Time 1016 - 16s later)
        with patch('time.time', return_value=1016.0):
            # We need to send another chunk to trigger the check
            new_segments = [self.create_segment("More text here.", 6.0, 7.0)]
            self.manager.on_transcript_chunk("Input 1 More text here.", segments + new_segments)
            
        self.mock_callback.assert_called_once()

    def test_trigger_on_character_threshold(self):
        """Ensure analysis IS triggered if buffer gets very full."""
        # Create a long text > 500 chars
        long_text = "word " * 100  # 500 chars
        segments = [self.create_segment(long_text, 0.0, 10.0)]
        
        with patch('time.time', return_value=1000.0):
            self.manager.last_analysis_time = 1000.0
            self.manager.on_transcript_chunk(long_text, segments)
            
        self.mock_callback.assert_called_once()

    def test_context_rotation(self):
        """Ensure buffers rotate correctly after analysis."""
        # Fill active buffer
        seg1 = self.create_segment("Segment 1", 0.0, 1.0)
        self.manager.active_buffer = [Segment.from_dict(seg1)]
        
        # Rotate
        self.manager.rotate_buffers()
        
        # Active should be empty, Context should have Segment 1
        self.assertEqual(len(self.manager.active_buffer), 0)
        self.assertEqual(len(self.manager.context_buffer), 1)
        self.assertEqual(self.manager.context_buffer[0].text, "Segment 1")

if __name__ == '__main__':
    unittest.main()
