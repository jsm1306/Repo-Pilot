import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

class RepoPilotLLM:
    def __init__(self, model="openai/gpt-oss-20b"):
        self.llm = ChatGroq(
            model=model,
            temperature=0.2,
            api_key=os.getenv("GROQ_API_KEY")
        )

        self.prompt = ChatPromptTemplate.from_template("""
You are RepoPilot, an AI repository analysis assistant.

Answer the user's question using only the provided repository context.

If the context does not contain enough information, say so clearly.

Mention relevant file paths and symbols when possible.

Repository context:
{context}

User question:
{question}
""")

        self.chain = (
            self.prompt
            | self.llm
            | StrOutputParser()
        )

    def generate(self, question, context):
        return self.chain.invoke({
            "question": question,
            "context": context
        })
    def generate_from_documents(self, question, documents):
        context_parts = []

        for document in documents:
            context_parts.append(
                f"""File: {document.metadata['file_path']}
    Symbol: {document.metadata.get('symbol', '')}
    Type: {document.metadata.get('symbol_type', '')}
    Language: {document.metadata.get('language', '')}
    Lines: {document.metadata['start_line']}-{document.metadata['end_line']}
    {document.page_content}"""
            )

        context = "\n\n---\n\n".join(context_parts)

        return self.chain.invoke({
            "question": question,
            "context": context
        })