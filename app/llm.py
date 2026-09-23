import os
from pathlib import Path

from groq import Groq
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

class GroqLLM:
    def __init__(self,model="openai/gpt-oss-20b"):
        api_key=os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is missing. Add it to app/.env or the process environment.")
        self.client=Groq(api_key=api_key)
        self.model=model

    def generate(self,question,context):
        prompt=f"""You are RepoPilot, an AI repository analysis assistant.

Answer the user's question using only the provided repository context.

If the context does not contain enough information, say so clearly.

Mention relevant file paths and symbols when possible.

Repository context:
{context}

User question:
{question}
"""
        response=self.client.chat.completions.create(
            model=self.model,
            messages=[{"role":"user","content":prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content