"""
SIM-TRUNK-ийн скриптийг (ingest, autogen, TTS, сургалт ...) МАНАЙ байгууллагын хавтас дээр ажиллуулна.

SIM-TRUNK-ийн tenant.py байгууллагын хавтсыг үргэлж SIM-TRUNK/tenants/<slug> гэж үздэг (TENANTS_DIR тогтмол).
Энэ wrapper tenant.TENANTS_DIR-ийг манай backend/data/tenants руу заагаад скриптийг ажиллуулна:
мэдээллийг манайхаас уншиж, индекс / аудио / сургалтыг манайд бичнэ. SIM-TRUNK-ийн өөрийн
байгууллагуудад (pinecone гэх мэт) хүрэхгүй. TTS кэш (SIM-TRUNK/data/tts_cache) нийтлэг хэвээр.

  <SIM-TRUNK>/.venv/bin/python backend/sim_runner.py <SIM-TRUNK хавтас> <манай tenants хавтас> <скрипт> [аргумент...]
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv: list[str]):
    sim_root, tenants_dir, script, *args = argv
    sim_root, tenants_dir = os.path.abspath(sim_root), os.path.abspath(tenants_dir)
    # Манай backend-д ижил нэртэй модуль (tenant, db, speech ...) бий -> SIM-TRUNK-ийнхийг л ачаална
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != HERE]
    sys.path[:0] = [sim_root, os.path.join(sim_root, "scripts")]
    os.chdir(sim_root)

    import tenant  # SIM-TRUNK/tenant.py — скриптүүд дахин import хийхэд яг энэ модуль ирнэ
    tenant.TENANTS_DIR = tenants_dir

    path = os.path.join(sim_root, script)
    sys.argv = [path, *args]
    runpy.run_path(path, run_name="__main__")


if __name__ == "__main__":
    main(sys.argv[1:])
