"""Утасны AI, вэб хоёр backend/speech_parse.py-ийн нэг задлагчийг ашиглана."""
import importlib.util
import os
import sys

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "speech_parse.py")
_spec = importlib.util.spec_from_file_location("speech_parse", _PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["speech_parse"] = _mod
_spec.loader.exec_module(_mod)
