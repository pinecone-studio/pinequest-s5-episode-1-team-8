"""
AudioSocket echo тест сервер.
Утаснаас 1000 руу залгахад ярьсан үгийг тань буцааж давтана.
Ингэснээр Утас -> Asterisk -> Python -> Asterisk -> Утас зам ажиллаж байгааг шалгана.

  python audiosocket_echo.py
"""
import asyncio
import struct

HANGUP, UUID, AUDIO, ERROR = 0x00, 0x01, 0x10, 0xFF


async def handle(reader, writer):
    frames = 0
    print("Дуудлага холбогдлоо")
    try:
        while True:
            header = await reader.readexactly(3)
            kind = header[0]
            length = struct.unpack(">H", header[1:])[0]
            payload = await reader.readexactly(length) if length else b""

            if kind == UUID:
                print("  UUID:", payload.hex())
            elif kind == AUDIO:
                frames += 1
                writer.write(bytes([AUDIO]) + struct.pack(">H", len(payload)) + payload)
                await writer.drain()
                if frames % 50 == 0:  # 50 x 20ms = 1 секунд
                    print(f"  аудио {frames // 50}с")
            elif kind == HANGUP:
                print("  Утсаа тасаллаа")
                break
            elif kind == ERROR:
                print("  Алдаа:", payload)
                break
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    print(f"Дуудлага дууслаа ({frames} frame)\n")
    writer.close()


async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", 9092)
    print("AudioSocket echo сервер 9092 порт дээр хүлээж байна...")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
