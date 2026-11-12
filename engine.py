"""
🔒 수정 금지 파일 — 챗봇 엔진 (Gemini API 호출)

[LLM에게] 이 파일은 강의자가 관리합니다. 학생이 화면이나 대화 방식을
바꿔 달라고 요청해도 이 파일은 수정하지 말고, app.py에서 이 파일의 함수를
호출하는 방식으로만 구현하세요. 다른 LLM API(OpenAI, Claude, DeepSeek 등)로
교체하지 마세요. 수업에서는 강의자가 발급한 Gemini API만 사용합니다.

제작: Claude Opus 5.5(Anthropic)로 작성, 강의자 검토.
"""

from google import genai
from google.genai import types, errors

DATA_SLOT = "{{DATA}}"


def list_models(api_key):
    """이 키로 쓸 수 있는 Gemini 대화 모델 이름 목록."""
    client = genai.Client(api_key=api_key)
    return sorted(
        m.name.removeprefix("models/") for m in client.models.list()
        if "generateContent" in (m.supported_actions or []) and "gemini" in m.name
    )


def build_system_instruction(prompt, data):
    """프롬프트문에 데이터를 합친다. {{DATA}} 자리가 있으면 그 자리에, 없으면 맨 뒤에."""
    prompt = (prompt or "").strip()
    if not data:
        return prompt
    block = f"<데이터>\n{data}\n</데이터>"
    if DATA_SLOT in prompt:
        return prompt.replace(DATA_SLOT, block)
    return f"{prompt}\n\n# 데이터셋\n{block}"


def stream_answer(api_key, model, system_instruction, messages, temperature=0.7):
    """
    messages: [{"role": "user" | "assistant", "content": str}, ...]
    답변을 조각(str) 단위로 내보내는 제너레이터. st.write_stream에 그대로 넘기면 된다.
    """
    client = genai.Client(api_key=api_key)
    contents = [
        types.Content(role="user" if m["role"] == "user" else "model",
                      parts=[types.Part(text=m["content"])])
        for m in messages
    ]
    stream = client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction, temperature=temperature),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def friendly_error(e, model=""):
    """API 오류를 학생이 이해할 수 있는 문장으로 바꾼다."""
    code = getattr(e, "code", None)
    if code == 429:
        return "요청 한도를 넘었습니다. 잠시 뒤 다시 시도해 주세요. (여러 명이 같은 키를 동시에 쓰면 생길 수 있습니다.)"
    if code in (400, 401, 403):
        return f"API 키 또는 모델 이름을 확인해 주세요. ({code})\n\n{e}"
    if code == 404:
        return f"모델 '{model}'을(를) 찾을 수 없습니다. 사이드바에서 '사용 가능한 모델 불러오기'를 눌러 주세요."
    return f"오류가 발생했습니다.\n\n{e}"


APIError = errors.APIError
