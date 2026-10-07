"""Нийтлэг тохиргоо. Бүх өгөгдөл DATA_DIR-д (git-д орохгүй); тест түр хавтас ашиглана.

SIM_TRUNK_LIVE=1 (./dev.sh --sim): байгууллагуудыг SIM-TRUNK-ийн хавтаснаас (SIM-TRUNK/tenants) шууд уншиж
бичнэ. Утасны систем (sip_bridge, phone_server) яг эдгээрийг ашигладаг тул дуудлага, бүртгэл, мэдээлэл, аудио,
ElevenLabs түлхүүр SIM-TRUNK-тэй нэг — SIM-TRUNK-ийн вэбийн оронд ажиллана.
Хэрэглэгчид (accounts.db), session-ий түлхүүр DATA_DIR-д хэвээр.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(HERE, "data"))
LIVE = os.getenv("SIM_TRUNK_LIVE") == "1"
SIM_TRUNK_DIR = os.path.abspath(os.getenv("SIM_TRUNK_DIR") or os.path.join(os.path.dirname(os.path.dirname(HERE)), "SIM-TRUNK"))
TENANTS_DIR = os.path.join(SIM_TRUNK_DIR, "tenants") if LIVE else os.path.join(DATA_DIR, "tenants")
