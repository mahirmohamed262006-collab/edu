import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

from chatbot_config import SYSTEM_PROMPT


load_dotenv()

app = Flask(__name__)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")


def get_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add your Gemini API key to .env."
        )

    return genai.Client(api_key=api_key)


def clean_history(history):
    if not isinstance(history, list):
        return []

    cleaned = []

    for item in history[-12:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role in {"user", "assistant"} and isinstance(content, str):
            content = content.strip()

            if content:
                cleaned.append((role, content[:6000]))

    return cleaned


def build_prompt(message, history):
    parts = [SYSTEM_PROMPT, "\n\nConversation history:"]

    if history:
        for role, content in history:
            label = "Student" if role == "user" else "Education Assistant"
            parts.append(f"{label}: {content}")
    else:
        parts.append("No previous conversation.")

    parts.append(f"\nStudent's new question:\n{message}")
    parts.append(
        "\nAnswer the student's new question according to the system instructions."
    )

    return "\n".join(parts)


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()
        history = clean_history(data.get("history", []))

        if not message:
            return jsonify({"error": "Please enter a question."}), 400

        if len(message) > 6000:
            return jsonify({"error": "Please keep your question under 6000 characters."}), 400

        client = get_client()

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=build_prompt(message, history),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=1200,
            ),
        )

        answer = (response.text or "").strip()

        if not answer:
            answer = "I couldn't generate an answer. Please try asking your study question again."

        return jsonify({"answer": answer})

    except Exception as exc:
        app.logger.exception("Chat request failed")
        return jsonify({"error": str(exc)}), 500


@app.get("/health")
def health():
    return jsonify({"status": "ok", "model": MODEL_NAME})


if __name__ == "__main__":
    app.run(debug=True)
