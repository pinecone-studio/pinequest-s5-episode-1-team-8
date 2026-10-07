"""AI runtime-ийн скриптийг (ingest, autogen, TTS, сургалт ...) байгууллагын хавтас дээр ажиллуулна.

AI runtime-ийн tenant.py өөрийн root/tenants замыг ашигладаг. Энэ wrapper
tenant.TENANTS_DIR-ийг backend/data/tenants руу зааж, индекс/аудио/сургалтын
үр дүнг мөн энэ төслийн data хавтсанд бичүүлнэ.

  .venv/bin/python backend/sim_runner.py <runtime хавтас> <tenants хавтас> <скрипт> [аргумент...]
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv: list[str]):
    sim_root, tenants_dir, script, *args = argv
    sim_root, tenants_dir = os.path.abspath(sim_root), os.path.abspath(tenants_dir)
    # Вэб backend-д ижил нэртэй модуль бий -> тусгаарласан AI runtime-ийнхийг ачаална.
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != HERE]
    sys.path[:0] = [sim_root, os.path.join(sim_root, "scripts")]
    os.chdir(sim_root)

    import tenant  # AI runtime tenant.py — дараагийн import-ууд мөн үүнийг авна.
    tenant.TENANTS_DIR = tenants_dir

    path = os.path.join(sim_root, script)
    sys.argv = [path, *args]
    runpy.run_path(path, run_name="__main__")


if __name__ == "__main__":
    main(sys.argv[1:])
