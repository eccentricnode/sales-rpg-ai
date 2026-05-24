#!/usr/bin/env python3
"""
Startup wrapper for WhisperLiveKit that applies anti-hallucination
patches before running the server.
"""
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def apply_patches():
    """Patch FasterWhisperASR.transcribe to override hallucination-prone defaults.

    The original method hardcodes beam_size=5 and condition_on_previous_text=True
    as explicit kwargs before **self.transcribe_kargs. We can't just add to
    transcribe_kargs because Python raises "got multiple values for keyword argument".
    Instead we replace the entire transcribe method with corrected values.
    """
    try:
        import numpy as np
        from whisperlivekit.local_agreement.backends import FasterWhisperASR

        def patched_transcribe(self, audio: np.ndarray, init_prompt: str = "") -> list:
            segments, info = self.model.transcribe(
                audio,
                language=self.original_language,
                initial_prompt=init_prompt,
                beam_size=1,
                word_timestamps=True,
                condition_on_previous_text=False,
                no_repeat_ngram_size=3,
                repetition_penalty=1.3,
                suppress_blank=True,
                **self.transcribe_kargs,
            )
            return list(segments)

        FasterWhisperASR.transcribe = patched_transcribe
        logger.info(
            "Anti-hallucination patch applied: "
            "beam_size=1, condition_on_previous_text=False, "
            "no_repeat_ngram_size=3, repetition_penalty=1.3"
        )
    except Exception as e:
        logger.warning(f"Could not apply patches (non-fatal): {e}")


apply_patches()

# Run the actual server
from whisperlivekit.basic_server import main
sys.exit(main())
