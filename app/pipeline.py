# app/pipeline.py
import io, yaml, torch, re
from PIL import Image
from dataclasses import dataclass
from typing import Dict, Any, Optional

from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from .prompts import SYSTEM_PROMPT, USER_TEMPLATE

@dataclass
class GenCfg:
    max_new_tokens: int = 256
    do_sample: bool = True
    temperature: float = 1.0
    top_p: float = 1.0
    top_k: int = 50

class Explainer:
    def __init__(self, cfg_path: str = "config.yml"):
        with open(cfg_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        req_device = self.cfg.get("device", "auto")
        if req_device == "cuda":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        elif req_device in ("cpu", "auto"):
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.max_side = int(self.cfg.get("max_side", 896))
        self.model_id = self.cfg.get("qwen_model", "Qwen/Qwen2-VL-7B-Instruct")

        g = (self.cfg.get("gen") or {})
        self.gen = GenCfg(
            max_new_tokens=int(g.get("max_new_tokens", 256)),
            do_sample=bool(g.get("do_sample", True)),
            temperature=float(g.get("temperature", 1.0)),
            top_p=float(g.get("top_p", 1.0)),
            top_k=int(g.get("top_k", 50)),
        )

        dtype = torch.float16 if (self.device == "cuda") else torch.float32
        self.processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=True)
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            self.model_id,
            torch_dtype=dtype,
            device_map="auto",
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )

        if self.gen.do_sample:
            self.model.generation_config.update(
                do_sample=True,
                temperature=self.gen.temperature,
                top_p=self.gen.top_p,
                top_k=self.gen.top_k,
            )
        else:
            self.model.generation_config.update(
                do_sample=False
            )

    def _resize(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        scale = self.max_side / max(w, h)
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        return img

    def explain(self, img_bytes: bytes, user_query: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img = self._resize(img)

        sys_txt = SYSTEM_PROMPT if system_prompt is None else system_prompt
        usr_txt = USER_TEMPLATE.format(user_query=user_query)

        messages = [
            {"role": "system", "content": [{"type": "text", "text": sys_txt}]},
            {"role": "user", "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": usr_txt},
            ]},
        ]

        prompt = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=False,
        )

        inputs = self.processor(
            text=[prompt],
            images=[img],
            return_tensors="pt",
        ).to(self.model.device)

        gen_kwargs = dict(
            generation_config=self.model.generation_config,
            max_new_tokens=self.gen.max_new_tokens,
        )

        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                **gen_kwargs,
            )

        decoded = self.processor.batch_decode(output, skip_special_tokens=True)[0].strip()

        parts = [p.strip() for p in re.split(r"(?i)\b(system|user|assistant)\b", decoded) if p.strip()]
        answer = parts[-1] if parts else decoded

        return {"explanation": answer, "raw": decoded}
