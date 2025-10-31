import asyncio, edge_tts

async def main():
    text = "내가 들고 있는 건 뭐야?"
    voice = "ko-KR-SunHiNeural"  # 예: SunHi, InJoon 등
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save("kor.mp3")

asyncio.run(main())