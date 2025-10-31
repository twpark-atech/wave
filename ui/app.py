# ui/app.py
# - 텍스트 입력이 비어있으면: "녹음 버튼" 표시
# - 텍스트 입력이 한 글자라도 있으면: 같은 자리의 버튼이 "전송 버튼"으로 바뀜
# - 이미지 없이 전송/녹음 완료 시도 시: status_placeholder에 "이미지를 입력하세요."만 표시하고 처리 중단
# - 미리보기는 "이미지 업로드"에서만 표시(웹캠 스냅샷 선택 시 미리보기 없음)
# - streamlit-mic-recorder는 호환 최소 인자만 사용

import io
import requests
import streamlit as st
from PIL import Image

BACKEND_URL = "http://localhost:8000/infer"

st.set_page_config(
    page_title="Atech Vision-LLM",
    page_icon="logo.png",
    layout="wide"
)

# 상단
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.image("logo.png", use_column_width=True)
with col_title:
    st.title("설명 결과")

left, right = st.columns([1, 1])

# -------------------- 좌측: 이미지 입력 --------------------
with left:
    st.subheader("이미지 입력")
    img_mode = st.radio("방식", ["웹캠 스냅샷", "이미지 업로드"], horizontal=True)

    img_file = None
    if img_mode == "웹캠 스냅샷":
        img_file = st.camera_input("카메라로 촬영")
    else:
        img_file = st.file_uploader("이미지 업로드", type=["jpg", "jpeg", "png", "bmp", "webp"])
        st.markdown("##### 미리보기")
        if img_file is not None:
            try:
                img_bytes = img_file.getvalue()
                img = Image.open(io.BytesIO(img_bytes))
                st.image(img, use_column_width=True)
            except Exception:
                st.image(img_file, use_column_width=True)
        else:
            st.info("이미지를 업로드하면 여기에서 미리보기가 표시됩니다.")

# -------------------- 우측: 질문 + 단일 액션 영역(전송/녹음 토글) --------------------
with right:
    st.subheader("질문")
    status_placeholder = st.empty()
    result_placeholder = st.empty()

    # 텍스트 입력: 내용 유무에 따라 아래 액션 영역이 전송/녹음으로 토글됨
    user_query = st.text_input(
        "텍스트를 입력하면 아래 버튼이 '전송'으로 바뀝니다. 비워두면 '녹음' 버튼이 나타납니다.",
        key="user_query_input",
        placeholder="텍스트 질문을 입력하거나 비워두면 음성 녹음을 사용합니다.",
    )

    action_area = st.container()

    # --- 텍스트가 있으면: 전송 버튼 ---
    if (user_query or "").strip():
        with action_area:
            if st.button("📤 전송", use_container_width=True):
                if img_file is None:
                    status_placeholder.error("이미지를 입력하세요.")
                else:
                    status_placeholder.info("요청 전송 중...")
                    files = {"image": ("frame.jpg", img_file.getvalue(), "image/jpeg")}
                    data = {"user_query": user_query}
                    try:
                        r = requests.post(BACKEND_URL, files=files, data=data, timeout=180)
                    except Exception as e:
                        status_placeholder.error(f"요청 실패: {e}")
                    else:
                        ct = r.headers.get("content-type", "")
                        if r.status_code != 200:
                            status_placeholder.error(f"백엔드 응답 오류: {r.status_code}")
                            result_placeholder.code(r.text[:1000])
                        elif "application/json" not in ct:
                            status_placeholder.error(f"JSON이 아닌 응답(Content-Type={ct})")
                            result_placeholder.code(r.text[:1000])
                        else:
                            try:
                                res = r.json()
                            except Exception as e:
                                status_placeholder.error(f"JSON 파싱 실패: {e}")
                                result_placeholder.code(r.text[:1000])
                            else:
                                status_placeholder.success("완료")
                                result_placeholder.write(res.get("explanation", "(no text)"))

    # --- 텍스트가 비어있으면: 녹음 버튼 ---
    else:
        with action_area:
            from streamlit_mic_recorder import mic_recorder
            st.caption("텍스트를 비워두면 음성 녹음 버튼이 표시됩니다. 녹음 후 자동 전송됩니다.")

            rec = mic_recorder(
                start_prompt="🎤 눌러서 녹음 시작",
                stop_prompt="⏹ 눌러서 녹음 중지",
                key="mic_rec_key",
                just_once=False,
                use_container_width=True,
                format="wav",
            )

            # 반환 처리 (버전에 따라 dict 또는 bytes)
            audio_bytes = None
            if isinstance(rec, dict):
                audio_bytes = rec.get("bytes") or rec.get("audio")
            elif isinstance(rec, (bytes, bytearray)):
                audio_bytes = bytes(rec)

            # 녹음이 끝나면 즉시 전송 시도
            if audio_bytes is not None:
                if img_file is None:
                    status_placeholder.error("이미지를 입력하세요.")
                else:
                    status_placeholder.info("요청 전송 중...")
                    files = {
                        "image": ("frame.jpg", img_file.getvalue(), "image/jpeg"),
                        "audio": ("query.wav", audio_bytes, "audio/wav"),
                    }
                    data = {"user_query": ""}

                    try:
                        r = requests.post(BACKEND_URL, files=files, data=data, timeout=180)
                    except Exception as e:
                        status_placeholder.error(f"요청 실패: {e}")
                    else:
                        ct = r.headers.get("content-type", "")
                        if r.status_code != 200:
                            status_placeholder.error(f"백엔드 응답 오류: {r.status_code}")
                            result_placeholder.code(r.text[:1000])
                        elif "application/json" not in ct:
                            status_placeholder.error(f"JSON이 아닌 응답(Content-Type={ct})")
                            result_placeholder.code(r.text[:1000])
                        else:
                            try:
                                res = r.json()
                            except Exception as e:
                                status_placeholder.error(f"JSON 파싱 실패: {e}")
                                result_placeholder.code(r.text[:1000])
                            else:
                                status_placeholder.success("완료")
                                result_placeholder.write(res.get("explanation", "(no text)"))
