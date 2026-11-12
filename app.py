"""
디지털인문학응용 — 데이터셋 기반 챗봇 실습 틀 (app.py)

[학생에게] 이 파일은 열지 않아도 됩니다.
  우리 조 챗봇은 team_config.py와 텍스트 파일(prompt.txt, data.ttl, greeting.txt,
  questions.txt, notice.txt)만 채우면 완성됩니다. 자세한 방법은 README.md를 보세요.

이 앱은 두 가지 화면으로 동작합니다.
  - 실습 모드(기본): 저장소의 prompt.txt·data.ttl을 불러와 시험하고, 화면에서 고치거나
    다른 파일을 올려 볼 수 있는 화면
  - 전시 모드: 저장소 파일만으로 동작하며, 참여자는 바로 대화만 하는 화면
    (team_config.py의 EXHIBIT_MODE = True, 또는 앱 Secrets에 EXHIBIT_MODE = true)

────────────────────────────────────────────────────────────────
[LLM에게 — 이 파일을 수정할 때 지켜 주세요]
학생은 이 앱을 자기 조의 챗봇 컨셉에 맞게 변형하려고 합니다.
대부분의 설정은 team_config.py와 텍스트 파일에서 바꿉니다. 이 파일은 화면 구성을
더 바꾸고 싶을 때만 수정합니다.

✏️ 수정해도 되는 곳
  - "✏️" 표시가 붙은 화면 구성 부분(문구, 배치, 버튼 추가, 시작 화면,
    추천 질문, 딜레마 선택 버튼, 대화 상대 선택, 대화 모드 등)
  - 새로운 화면 요소를 추가하는 것

🔒 수정하지 말아야 할 곳
  - engine.py, ttl_to_text.py 파일 전체 (강의자 관리)
  - "🔒" 표시가 붙은 부분: 설정·파일 불러오기, API 키 처리, 프롬프트문·ttl 입력 처리,
    전시 모드 처리, 엔진 호출
  - 다른 LLM API로 교체하는 것 (수업에서는 강의자가 발급한 Gemini API만 사용)
  - 화면 맨 아래 AI 사용 표기(footer)를 지우는 것
    (조에서 AI를 써서 변형했다면 team_config.py의 AI_USE_NOTE에 그 사실을 적습니다)
  - API 키를 이 파일이나 저장소의 어떤 파일에도 적는 것
    (키는 Streamlit 앱 설정의 Secrets에만 넣습니다)
────────────────────────────────────────────────────────────────

제작: 이 템플릿은 Claude Opus 5.5(Anthropic)로 작성하고 강의자가 검토했습니다.
"""

from datetime import datetime
from pathlib import Path

import streamlit as st

import engine
from ttl_to_text import parse_ttl, graph_to_text


# ───────────────── 🔒 고정 값 ─────────────────
TEMPLATE_CREDIT = "본 실습 틀은 Claude Opus 5.5(Anthropic)로 제작하고 강의자가 검토했습니다."
APP_DIR = Path(__file__).parent
DATA_MODE_TEXT = "문장으로 풀어서 전달 (권장)"
EXHIBIT_BUSY_MESSAGE = ("지금 대화하는 분이 많아 응답이 늦어지고 있습니다. 잠시 후 다시 입력해 주십시오.  \n"
                        "Many people are chatting right now. Please try again in a moment.")
EXHIBIT_ERROR_MESSAGE = "일시적인 문제로 답변하지 못했습니다. 잠시 후 다시 입력해 주십시오."
EXHIBIT_RESET_LABEL = "새 대화 시작"
MAX_QUESTIONS = 6


# ───────────────── 🔒 우리 조 설정(team_config.py) 불러오기 ─────────────────
DEFAULTS = {
    "APP_TITLE": "데이터셋 챗봇 실습", "APP_SUBTITLE": "", "PAGE_ICON": "💬",
    "BOT_NAME": "챗봇", "BOT_AVATAR": "", "CHAT_PLACEHOLDER": "챗봇에게 질문해 보세요",
    "MODEL": "gemini-2.5-flash-lite", "TEMPERATURE": 0.7,
    "EXHIBIT_MODE": False, "AI_USE_NOTE": "",
}
config_problems = []
try:
    # 매번 파일에서 새로 읽어, team_config.py를 고치면 바로 반영되게 한다.
    _ns = {}
    _src = (APP_DIR / "team_config.py").read_text(encoding="utf-8-sig")
    exec(compile(_src, "team_config.py", "exec"), _ns)
    cfg = {k: _ns.get(k, v) for k, v in DEFAULTS.items()}
except Exception as e:  # 파일이 없거나 문법 오류
    cfg = dict(DEFAULTS)
    line = f" ({getattr(e, 'lineno', '?')}번째 줄)" if isinstance(e, SyntaxError) else ""
    config_problems.append(f"team_config.py를 읽지 못했습니다{line}. 따옴표나 괄호가 빠지지 않았는지 확인하세요. [{e}]")

for k in ("APP_TITLE", "APP_SUBTITLE", "PAGE_ICON", "BOT_NAME", "BOT_AVATAR", "CHAT_PLACEHOLDER", "MODEL", "AI_USE_NOTE"):
    if cfg[k] is None:
        cfg[k] = ""
    if not isinstance(cfg[k], str):
        config_problems.append(f"{k}는 따옴표로 감싼 글자여야 합니다. 지금 값: {cfg[k]!r}")
        cfg[k] = DEFAULTS[k]
try:
    cfg["TEMPERATURE"] = float(cfg["TEMPERATURE"])
    if not 0.0 <= cfg["TEMPERATURE"] <= 2.0:
        raise ValueError
except (TypeError, ValueError):
    config_problems.append(f"TEMPERATURE는 0.0 ~ 2.0 사이 숫자여야 합니다. 지금 값: {cfg['TEMPERATURE']!r} → 0.7로 대신 실행합니다.")
    cfg["TEMPERATURE"] = 0.7
if not cfg["MODEL"].strip():
    config_problems.append("MODEL이 비어 있습니다. 기본 모델로 실행합니다.")
    cfg["MODEL"] = DEFAULTS["MODEL"]
if not isinstance(cfg["EXHIBIT_MODE"], bool):
    config_problems.append(f"EXHIBIT_MODE는 True 또는 False여야 합니다(따옴표 없이). 지금 값: {cfg['EXHIBIT_MODE']!r}")
    cfg["EXHIBIT_MODE"] = False


# ───────────────── 🔒 텍스트 파일 불러오기 ─────────────────
def read_repo_text(name):
    f = APP_DIR / name
    return f.read_text(encoding="utf-8-sig").strip() if f.exists() else ""


def repo_data_files():
    return sorted(p.name for p in APP_DIR.glob("data*.ttl"))


GREETING = read_repo_text("greeting.txt")
SUGGESTED_QUESTIONS = [q.strip() for q in read_repo_text("questions.txt").splitlines() if q.strip()]
if len(SUGGESTED_QUESTIONS) > MAX_QUESTIONS:
    config_problems.append(f"questions.txt의 추천 질문이 {len(SUGGESTED_QUESTIONS)}개입니다. 앞의 {MAX_QUESTIONS}개만 보여 줍니다.")
    SUGGESTED_QUESTIONS = SUGGESTED_QUESTIONS[:MAX_QUESTIONS]
NOTICE = read_repo_text("notice.txt")
REPO_PROMPT = read_repo_text("prompt.txt")
REPO_DATA_FILES = repo_data_files()

APP_TITLE, APP_SUBTITLE = cfg["APP_TITLE"], cfg["APP_SUBTITLE"]
BOT_NAME, CHAT_PLACEHOLDER = cfg["BOT_NAME"], cfg["CHAT_PLACEHOLDER"]
BOT_AVATAR = cfg["BOT_AVATAR"] or None
AI_USE_NOTE = cfg["AI_USE_NOTE"]


# ───────────────── 🔒 Secrets 읽기 · 전시 모드 판정 ─────────────────
def read_secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def secret_flag(name):
    v = read_secret(name, False)
    return v is True or str(v).strip().lower() in ("true", "1", "yes", "on")


EXHIBIT = cfg["EXHIBIT_MODE"] or secret_flag("EXHIBIT_MODE")

st.set_page_config(page_title=APP_TITLE, page_icon=cfg["PAGE_ICON"] or "💬", layout="wide",
                   initial_sidebar_state="collapsed" if EXHIBIT else "auto")

ss = st.session_state
ss.setdefault("messages", [])
ss.setdefault("models", [])


@st.cache_data(show_spinner=False)
def load_repo_data(names, stamp):
    """저장소의 ttl을 읽어 (트리플 수, 문장형 텍스트, 원문, 오류)를 돌려준다. stamp는 파일 변경 감지용."""
    files = [(n, (APP_DIR / n).read_bytes()) for n in names]
    g, errs = parse_ttl(files)
    raw = "\n\n".join(b.decode("utf-8", "ignore") for _, b in files)
    return len(g), (graph_to_text(g) if len(g) else ""), raw, errs


def file_stamp(names):
    return "|".join(f"{n}:{(APP_DIR / n).stat().st_mtime}" for n in names if (APP_DIR / n).exists())


# ───────────────── 🔒 사이드바: API 키·모델 설정 (실습 모드) ─────────────────
if EXHIBIT:
    api_key = read_secret("GEMINI_API_KEY", "")
    model = cfg["MODEL"]
    temperature = cfg["TEMPERATURE"]
    data_mode = DATA_MODE_TEXT
else:
    with st.sidebar:
        st.header("1. API 키")
        api_key = st.text_input("강의자가 제공한 API 키", type="password",
                                help="키는 이 브라우저 세션에서만 쓰이고 저장되지 않습니다.")
        if not api_key:
            api_key = read_secret("GEMINI_API_KEY", "")
            if api_key:
                st.caption("강의자 설정 키를 사용합니다.")

        st.header("모델 설정")
        if st.button("사용 가능한 모델 불러오기", disabled=not api_key, use_container_width=True):
            try:
                ss.models = engine.list_models(api_key)
                st.success(f"모델 {len(ss.models)}개를 불러왔습니다.")
            except Exception as e:
                st.error(f"모델 목록을 불러오지 못했습니다. API 키를 확인해 주세요.\n\n{e}")

        if ss.models:
            idx = ss.models.index(cfg["MODEL"]) if cfg["MODEL"] in ss.models else 0
            model = st.selectbox("모델", ss.models, index=idx)
        else:
            model = st.text_input("모델", value=cfg["MODEL"])

        temperature = st.slider("temperature (답변의 다양성)", 0.0, 2.0, cfg["TEMPERATURE"], 0.1,
                                help="낮을수록 같은 질문에 비슷하게, 높을수록 다양하게 답합니다.")
        data_mode = st.radio("데이터 전달 방식", [DATA_MODE_TEXT, "ttl 원문 그대로 전달"])

        st.divider()
        if st.button("대화 초기화", use_container_width=True):
            ss.messages = []
            st.rerun()


# ───────────────── ✏️ 상단 제목 (문구·배치 수정 가능) ─────────────────
st.title(APP_TITLE)
if APP_SUBTITLE:
    st.caption(APP_SUBTITLE)
if EXHIBIT and NOTICE:
    st.info(NOTICE)


# ───────────────── 🔒 설정 점검 ─────────────────
if EXHIBIT:
    for p in config_problems:
        st.error(f"[관리자 확인 필요] {p}")
else:
    with st.expander("우리 조 설정 확인" + (" — ⚠️ 확인할 곳이 있습니다" if config_problems else ""),
                     expanded=bool(config_problems)):
        for p in config_problems:
            st.error(p)
        st.markdown("\n".join([
            f"- 제목: **{APP_TITLE}** / 챗봇 이름: **{BOT_NAME}**",
            f"- 모델: `{cfg['MODEL']}` / temperature: `{cfg['TEMPERATURE']}`",
            f"- 전시 모드: {'켜짐' if EXHIBIT else '꺼짐'}",
            f"- prompt.txt: {'불러옴 (' + format(len(REPO_PROMPT), ',') + '자)' if REPO_PROMPT else '없음'}",
            f"- 데이터 파일: {', '.join(REPO_DATA_FILES) if REPO_DATA_FILES else '없음'}",
            f"- greeting.txt: {'있음' if GREETING else '없음'}",
            f"- questions.txt: 추천 질문 {len(SUGGESTED_QUESTIONS)}개",
            f"- notice.txt: {'있음 (전시 모드에서 표시)' if NOTICE else '없음'}",
        ]))


# ───────────────── 🔒 프롬프트문·데이터 입력 ─────────────────
if EXHIBIT:
    prompt_text = REPO_PROMPT
    data_text = ""
    if not REPO_PROMPT:
        st.error("[관리자 확인 필요] 저장소에 prompt.txt가 없거나 비어 있습니다.")
    if REPO_DATA_FILES:
        n, data_text, _, errs = load_repo_data(tuple(REPO_DATA_FILES), file_stamp(REPO_DATA_FILES))
        for e in errs:
            st.error(f"[관리자 확인 필요] {e}")
    else:
        st.error("[관리자 확인 필요] 저장소에 data.ttl이 없습니다.")
else:
    col_p, col_d = st.columns(2)

    with col_p:
        st.subheader("2. 프롬프트문")
        if "prompt_text" not in ss and REPO_PROMPT:
            ss.prompt_text = REPO_PROMPT
        up = st.file_uploader("다른 프롬프트 파일로 시험하기 (.txt, .md)", type=["txt", "md"], key="prompt_file")
        if up is not None and ss.get("prompt_loaded") != up.file_id:
            ss.prompt_text = up.getvalue().decode("utf-8-sig")
            ss.prompt_loaded = up.file_id
        if REPO_PROMPT:
            st.caption("저장소의 prompt.txt를 불러왔습니다. 여기서 고친 내용은 시험용이며 저장소 파일은 바뀌지 않습니다.")
        prompt_text = st.text_area(
            "프롬프트문", key="prompt_text", height=300,
            placeholder="예) 너는 ○○다. 사용자는 △△다.\n아래 데이터에 있는 내용만 사실로 말한다.\n\n"
                        f"데이터가 들어갈 자리를 {engine.DATA_SLOT} 로 표시할 수 있습니다. 표시가 없으면 맨 뒤에 붙습니다.",
        )

    with col_d:
        st.subheader("3. 데이터셋 ttl")
        ttl_files = st.file_uploader("다른 ttl 파일로 시험하기 (여러 개 가능)", type=["ttl"], accept_multiple_files=True)
        data_text, n_triples, raw = "", 0, ""
        if ttl_files:
            g, errs = parse_ttl([(f.name, f.getvalue()) for f in ttl_files])
            for e in errs:
                st.error(e)
            n_triples = len(g)
            raw = "\n\n".join(f.getvalue().decode("utf-8", "ignore") for f in ttl_files)
            text = graph_to_text(g) if n_triples else ""
            source = "올린 파일"
        elif REPO_DATA_FILES:
            n_triples, text, raw, errs = load_repo_data(tuple(REPO_DATA_FILES), file_stamp(REPO_DATA_FILES))
            for e in errs:
                st.error(e)
            source = "저장소의 " + ", ".join(REPO_DATA_FILES)
        if n_triples:
            data_text = text if data_mode.startswith("문장") else raw
            st.success(f"{source}에서 트리플 {n_triples:,}개를 읽었습니다.")
            with st.expander("챗봇에게 전달되는 데이터 미리보기"):
                st.caption(f"{len(data_text):,}자")
                st.code(data_text, language="markdown" if data_mode.startswith("문장") else "turtle")

system_instruction = engine.build_system_instruction(prompt_text, data_text)

if not EXHIBIT:
    with st.expander("최종 시스템 지시문 확인 (프롬프트문 + 데이터)"):
        st.text(system_instruction or "아직 입력된 내용이 없습니다.")


# ───────────────── ✏️ 대화 화면 (배치·문구·버튼 수정 가능) ─────────────────
st.divider()
if not EXHIBIT:
    st.subheader("4. 대화")

if EXHIBIT:
    missing = [] if (api_key and prompt_text.strip()) else ["설정"]
    if not api_key:
        st.error("[관리자 확인 필요] 전시용 API 키가 앱 Secrets에 설정되어 있지 않습니다.")
    if st.button(EXHIBIT_RESET_LABEL):
        ss.messages = []
        st.rerun()
else:
    missing = [n for n, v in [("API 키", api_key), ("프롬프트문", prompt_text.strip())] if not v]
    if missing:
        st.info("다음 항목을 입력하면 대화를 시작할 수 있습니다: " + ", ".join(missing))
    elif not data_text:
        st.warning("데이터셋 ttl 없이 대화합니다. 챗봇은 프롬프트문만 보고 답합니다.")

if GREETING and not ss.messages:
    ss.messages.append({"role": "assistant", "content": GREETING})

for m in ss.messages:
    with st.chat_message(m["role"], avatar=BOT_AVATAR if m["role"] == "assistant" else None):
        st.markdown(m["content"])

# ✏️ 추천 질문 버튼
clicked = None
if SUGGESTED_QUESTIONS and not missing:
    cols = st.columns(len(SUGGESTED_QUESTIONS))
    for i, (c, q) in enumerate(zip(cols, SUGGESTED_QUESTIONS)):
        if c.button(q, use_container_width=True, key=f"suggest_{i}"):
            clicked = q

typed = st.chat_input(CHAT_PLACEHOLDER, disabled=bool(missing))
question = clicked or typed


# ───────────────── 🔒 엔진 호출 (질문 → 답변) ─────────────────
def ask(q):
    ss.messages.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant", avatar=BOT_AVATAR):
        try:
            answer = st.write_stream(
                engine.stream_answer(api_key, model, system_instruction, ss.messages, temperature))
            ss.messages.append({"role": "assistant", "content": answer or ""})
        except engine.APIError as e:
            ss.messages.pop()
            if EXHIBIT:
                st.warning(EXHIBIT_BUSY_MESSAGE if getattr(e, "code", None) == 429 else EXHIBIT_ERROR_MESSAGE)
            else:
                st.error(engine.friendly_error(e, model))
        except Exception as e:
            ss.messages.pop()
            if EXHIBIT:
                st.warning(EXHIBIT_ERROR_MESSAGE)
            else:
                st.error(f"오류가 발생했습니다.\n\n{e}")


if question:
    ask(question)


# ───────────────── 🔒 대화 기록 내려받기 (실습 모드) ─────────────────
if not EXHIBIT and any(m["role"] == "user" for m in ss.messages):
    log = ["# 챗봇 대화 기록", f"- 일시: {datetime.now():%Y-%m-%d %H:%M}",
           f"- 모델: {model} / temperature: {temperature}", f"- 도구: {TEMPLATE_CREDIT}"]
    if AI_USE_NOTE:
        log.append(f"- 조별 변형: {AI_USE_NOTE}")
    log += ["", "## 프롬프트문", prompt_text.strip(), "", "## 대화"]
    for m in ss.messages:
        who = "사용자" if m["role"] == "user" else BOT_NAME
        log += [f"**{who}**: {m['content']}", ""]
    st.download_button("대화 기록 내려받기 (.md)", "\n".join(log).encode("utf-8"),
                       file_name=f"chatbot_log_{datetime.now():%Y%m%d_%H%M}.md", mime="text/markdown")


# ───────────────── 🔒 AI 사용 표기 (삭제 금지) ─────────────────
st.divider()
st.caption(TEMPLATE_CREDIT + (f" {AI_USE_NOTE}" if AI_USE_NOTE else ""))
