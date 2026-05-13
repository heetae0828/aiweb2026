import json
import os
from datetime import datetime
from pathlib import Path

import gradio as gr
import openai
from PyPDF2 import PdfReader
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY is required. Add it to .env or export it in the environment.")

HISTORY_PATH = Path("history.json")
MAX_HISTORY = 100


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history: list[dict]) -> None:
    history = history[-MAX_HISTORY:]
    with HISTORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def extract_text_from_pdf(path: str) -> str:
    try:
        with open(path, "rb") as f:
            reader = PdfReader(f)
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def extract_text_from_file(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def prepare_content(files: list[str]) -> str:
    texts = []
    for file_path in files or []:
        content = extract_text_from_file(file_path)
        if content:
            texts.append(f"---\nFile: {Path(file_path).name}\n---\n{content}")
    return "\n\n".join(texts)


def build_question_prompt(study_context: str, num_questions: int) -> str:
    return f"""
You are a smart study assistant for a student preparing for exams.

Use the provided study materials to generate exactly {num_questions} exam-style questions.
- Keep questions short and clear.
- Use numbered bullets.
- Do not include answers.

Study material:
{study_context}

If the material is empty, respond with a short message saying no valid study files were provided.
"""


def build_grading_prompt(question: str, answer: str, reference_text: str) -> str:
    return f"""
You are a helpful grader.

The student answered this question:
Question: {question}
Answer: {answer}

Reference material:
{reference_text}

Evaluate the answer and respond with JSON only.
The JSON object should include these keys:
- score: integer 0-100
- verdict: one of [Excellent, Good, Needs Improvement, Incorrect]
- feedback: concise feedback explaining why.
"""


def call_openai(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=900,
    )
    return response.choices[0].message.content.strip()


def generate_questions(study_files: list[str], num_questions: int) -> str:
    study_text = prepare_content(study_files)
    if not study_text.strip():
        return "No valid study files were found. Please upload PDF, TXT, or markdown files."

    prompt = build_question_prompt(study_text, num_questions)
    return call_openai(prompt)


def grade_answer(question: str, answer: str, reference_files: list[str]) -> tuple[str, list[dict]]:
    reference_text = prepare_content(reference_files)
    if not reference_text.strip():
        return "No valid reference files were found. Please upload file(s) to help grade the answer.", []

    prompt = build_grading_prompt(question, answer, reference_text)
    raw = call_openai(prompt)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return (
            "OpenAI 응답을 JSON으로 파싱할 수 없습니다. 응답을 그대로 표시합니다:\n" + raw,
            [],
        )

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "question": question,
        "answer": answer,
        "score": result.get("score", 0),
        "verdict": result.get("verdict", "Unknown"),
        "feedback": result.get("feedback", ""),
    }
    history = load_history()
    history.append(entry)
    save_history(history)

    grade_text = (
        f"**Score:** {entry['score']} / 100\n\n"
        f"**Verdict:** {entry['verdict']}\n\n"
        f"**Feedback:** {entry['feedback']}"
    )
    return grade_text, history


def summarize_history(history: list[dict]) -> str:
    if not history:
        return "No grading history yet. Practice questions and grade answers to build history."

    counts = {}
    for item in history:
        verdict = item.get("verdict", "Unknown")
        counts[verdict] = counts.get(verdict, 0) + 1

    lines = ["### Grading History Summary"]
    for verdict, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- **{verdict}**: {count}")

    lines.append("\nMost recent graded question:")
    last = history[-1]
    lines.append(f"- Question: {last.get('question')}")
    lines.append(f"- Score: {last.get('score')}")
    lines.append(f"- Verdict: {last.get('verdict')}")
    return "\n".join(lines)


def create_demo_interface() -> gr.Blocks:
    history = load_history()
    with gr.Blocks(title="Walrus Study") as demo:
        gr.Markdown("""
# Walrus Study

OpenAI 기반 문제 생성과 답안 채점 도우미입니다.
- 학습 자료 파일을 업로드하여 문제를 생성합니다.
- 참고 파일을 올려 답안을 채점하고 피드백을 받습니다.
- 채점 결과는 로컬 `history.json`에 저장됩니다.
""")

        with gr.Row():
            with gr.Column(scale=2):
                study_files = gr.File(label="학습 자료 업로드", file_count="multiple", type="file")
                num_questions = gr.Slider(1, 10, value=5, step=1, label="생성할 문제 수")
                generate_btn = gr.Button("문제 생성")
                question_output = gr.Textbox(label="생성된 문제", lines=10, interactive=False)

                gr.Markdown("---")
                question_text = gr.Textbox(label="채점할 문제", placeholder="문제를 직접 입력하거나 생성된 문제를 복사해서 붙여넣으세요.")
                answer_text = gr.Textbox(label="학생 답안", lines=6, placeholder="학생 답안을 여기에 입력합니다.")
                reference_files = gr.File(label="채점 참고 자료 업로드", file_count="multiple", type="file")
                grade_btn = gr.Button("답안 채점")
                grade_output = gr.Markdown(label="채점 결과")

            with gr.Column(scale=1):
                history_box = gr.Markdown(summarize_history(history), label="채점 히스토리")
                history_json = gr.Textbox(value=json.dumps(history[-20:], ensure_ascii=False, indent=2), label="최근 채점 기록(JSON)", lines=20)

        generate_btn.click(
            fn=generate_questions,
            inputs=[study_files, num_questions],
            outputs=[question_output],
        )

        def grade_and_refresh(question, answer, refs):
            result_text, updated_history = grade_answer(question, answer, refs)
            return result_text, summarize_history(updated_history), json.dumps(updated_history[-20:], ensure_ascii=False, indent=2)

        grade_btn.click(
            fn=grade_and_refresh,
            inputs=[question_text, answer_text, reference_files],
            outputs=[grade_output, history_box, history_json],
        )

    return demo


if __name__ == "__main__":
    create_demo_interface().launch(server_name="0.0.0.0", server_port=7860)
