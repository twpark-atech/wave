# app/server.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from .pipeline import Explainer

app = FastAPI(title="Vision Explainer")
pipe = Explainer(cfg_path="config.yml")

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/infer")
async def infer(image: UploadFile = File(...), user_query: str = Form(...)):
    img_bytes = await image.read()
    out = pipe.explain(img_bytes, user_query)
    return JSONResponse(out)