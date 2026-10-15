"""SMS илгээх — НЭГ эх сурвалж: ai_runtime/notify.py (send_sms). Вэбийн сануулга (reminders.py) үүгээр илгээнэ."""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "ai_notify", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_runtime", "notify.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
send_sms = _mod.send_sms
