# ui/app.py
import requests, streamlit as st

st.set_page_config(
    page_title="Atech Vision-LLM",
    page_icon="logo.png",
    layout="wide"
)

col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.image("logo.png", use_column_width=True)
with col_title:
    st.title("설명 결과")

left, right = st.columns([1, 1])

with left:
    st.subheader("이미지 입력")
    img_mode = st.radio("방식", ["웹캠 스냅샷", "이미지 업로드"], horizontal=True)
    if img_mode == "웹캠 스냅샷":
        img_file = st.camera_input("카메라로 촬영")
    else:
        img_file = st.file_uploader("이미지 업로드", type=["jpg", "jpeg", "png", "bmp", "webp"])

with right:
    st.subheader("질문 입력")
    qa_mode = st.radio("질문 방식", ["텍스트", "음성(녹음 버튼)"], horizontal=True)

    status_placeholder = st.empty()
    result_placeholder = st.empty()

    if qa_mode == "텍스트":
        user_query = st.text_input("여기에 질문을 입력하세요 (Enter로 전송)", key="user_query_input")

        if user_query and img_file is not None:
            status_placeholder.info("요청 전송 중...")
            files = {"image": ("frame.jpg", img_file.getvalue(), "image/jpeg")}
            data = {"user_query": user_query}
            try:
                r = requests.post("http://localhost:8000/infer", files=files, data=data, timeout=120)
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
        else:
            if img_file is None:
                status_placeholder.warning("이미지를 먼저 입력하세요.")
            elif not user_query:
                status_placeholder.info("질문을 입력하고 Enter를 누르면 즉시 전송합니다.")

    else:
        audio_bytes = None
        try:
            from st_audiorec import st_audiorec
            st.caption("아래 버튼을 눌러 녹음하고, 다시 누르면 종료됩니다.")
            audio_bytes = st_audiorec()
        except Exception:
            st.caption("녹음 컴포넌트가 없으면 파일 업로드를 사용하세요.")
            audio_file = st.file_uploader(
                "음성 파일 업로드", type=["wav", "mp3", "m4a", "ogg", "webm"]
            )
            if audio_file is not None:
                audio_bytes = audio_file.getvalue()
        
        if audio_bytes and img_file is not None:
            status_placeholder.info("요청 전송 중...")
            files = {
                "image": ("frame.jpg", img_file.getvalue(), "image/jpeg"),
                "audio": ("query.wav", audio_bytes, "audio/wav"),
            }
            data = {"user_query": ""}

            try:
                r = requests.post("http://localhost:8000/infer", files=files, data=data, timeout=180)
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
        else:
            if img_file is None:
                status_placeholder.warning("이미지를 먼저 입력하세요.")
            else:
                st.info("녹음 버튼으로 음성을 입력하거나 음성 파일을 업로드하세요.")