import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

class RepoPilotLLM:
    def __init__(self, model="openai/gpt-oss-20b"):
        self.llm = ChatGroq(
            model=model,
            temperature=0.2,
            api_key=os.getenv("GROQ_API_KEY")
        )

    def generate(self, question, context):
        prompt = f"""You are RepoPilot, an AI repository analysis assistant.

Answer the user's question using only the provided repository context.

If the context does not contain enough information, say so clearly.

Mention relevant file paths and symbols when possible.

Repository context:
{context}

User question:
{question}
"""
        response = self.llm.invoke(prompt)
        return response.content