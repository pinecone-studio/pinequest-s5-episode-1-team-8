"""
Хувийн RAG-ийн өгөгдлийн давхарга — НЭГ эх сурвалж: backend/people.py.

Утасны AI (энэ хавтас) болон вэб (backend/) нэг receptionist.db руу ЯГ нэг логикоор бичнэ. Хуулбар бүү үүсгэ:
өмнө нь хоёр хувилбар зөрж, утасны AI эвентийн "ирэх эсэх" баримтыг устгах, эвентийг уулзалт гэж андуурах,
дугаар солиход зөвхөн нэг бүртгэлийг шинэчлэх алдаа гардаг байсан.
"""
import importlib.util
import os
import sys

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "people.py")
_spec = importlib.util.spec_from_file_location("people", _PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["people"] = _mod        # `import people` -> backend/people.py
_spec.loader.exec_module(_mod)
_mod.EMBED_ON_WRITE = False         # утасны AI баримтын векторыг өөрийн bge-m3-аар хайлтын үед тооцоолно
