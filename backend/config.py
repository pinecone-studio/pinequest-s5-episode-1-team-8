"""Нийтлэг тохиргоо. Бүх өгөгдөл DATA_DIR-д (git-д орохгүй); тест түр хавтас ашиглана."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(HERE, "data"))
TENANTS_DIR = os.path.join(DATA_DIR, "tenants")
