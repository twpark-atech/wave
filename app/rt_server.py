# app/rt_server.py  (전체 교체)
import io, yaml, base64, asyncio, json, time
from typing import Optional
from PIL import Image
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketState
from .pipeline import Explainer  # ZeroShotExplainer → Explainer (explain(img_bytes, user_query))

app = FastAPI(title="Zero-shot Vision Explainer (RealTime)")
pipe = Explainer(cfg_path="config.yml")

# 로고 서빙 (프로젝트 루트의 logo.png)
@app.get("/logo.png")
async def get_logo():
    return FileResponse("logo.png")

# 단일 소비자 큐(프레임 과부하 방지): 최근 프레임만 유지
class LatestFrameQueue:
    def __init__(self):
        self._item: Optional[bytes] = None
        self._event = asyncio.Event()

    def put(self, item: bytes):
        self._item = item
        if not self._event.is_set():
            self._event.set()

    async def get(self) -> bytes:
        await self._event.wait()
        self._event.clear()
        return self._item

def decode_dataurl_image(data_url: str) -> bytes:
    # "data:image/webp;base64,...."
    header, b64 = data_url.split(",", 1)
    return base64.b64decode(b64)

async def transcribe_audio_stub(b64_data: str, mime: str) -> str:
    # TODO: STT 엔진(Whisper 등) 연결
    # 현재는 비워둠(서버가 텍스트를 못 만들면 기존 user_query 유지)
    return ""

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    q = LatestFrameQueue()
    running = True

    # 상태: 최신 텍스트 질문
    latest_query: str = ""

    async def producer():
        nonlocal running, latest_query
        try:
            while running and ws.application_state == WebSocketState.CONNECTED:
                msg = await ws.receive_text()

                # 하위호환: 순수 dataURL만 오는 경우(이전 클라이언트)
                if msg.startswith("data:image"):
                    img_bytes = decode_dataurl_image(msg)
                    q.put(img_bytes)
                    continue

                # 신규 프로토콜: JSON {type: "frame"|"text"|"audio", ...}
                try:
                    obj = json.loads(msg)
                except Exception:
                    continue

                mtype = obj.get("type")
                if mtype == "frame":
                    image_field = obj.get("image", "")
                    if isinstance(image_field, str) and image_field.startswith("data:image"):
                        img_bytes = decode_dataurl_image(image_field)
                        q.put(img_bytes)
                elif mtype == "text":
                    latest_query = str(obj.get("user_query", "")).strip()
                elif mtype == "audio":
                    b64 = obj.get("data", "")
                    mime = obj.get("mime", "audio/webm")
                    if isinstance(b64, str) and b64:
                        text = await transcribe_audio_stub(b64, mime)
                        if text:
                            latest_query = text.strip()
                else:
                    # ignore unknown
                    pass
        except WebSocketDisconnect:
            running = False
        except Exception:
            running = False

    async def consumer():
        nonlocal running, latest_query
        try:
            throttle_ms = 600
            last_t = 0.0
            while running and ws.application_state == WebSocketState.CONNECTED:
                img_bytes = await q.get()
                now_ms = time.time() * 1000.0
                if now_ms - last_t < throttle_ms:
                    await asyncio.sleep((throttle_ms - (now_ms - last_t)) / 1000.0)

                t0 = time.time()
                # pipeline 호출: 최신 텍스트 질문 동봉
                out = pipe.explain(img_bytes=img_bytes, user_query=latest_query or "이게 뭐야?")
                dt_ms = int((time.time() - t0) * 1000)

                payload = json.dumps(
                    {"explanation": out.get("explanation", ""), "latency_ms": dt_ms},
                    ensure_ascii=False
                )
                await ws.send_text(payload)
                last_t = time.time() * 1000.0
        except WebSocketDisconnect:
            running = False
        except Exception:
            running = False

    await asyncio.gather(producer(), consumer())
