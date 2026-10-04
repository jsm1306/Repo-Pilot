import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import HumanMessage, ToolMessage
from app.tools import search_repository, read_repository_file
load_dotenv(Path(__file__).with_name(".env"))

class RepoPilotLLM:
    def __init__(self, model="openai/gpt-oss-20b"):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is missing. Add it to app/.env or the process environment.")

        self.llm = ChatGroq(
            model=model,
            temperature=0.2,
            api_key=api_key
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
    def bind_tools(self, tools):
        return self.llm.bind_tools(tools)

    def create_rag_chain(self, retriever):
        def format_documents(documents):
            return "\n\n---\n\n".join(
                f"""File: {doc.metadata['file_path']}
Symbol: {doc.metadata.get('symbol', '')}
Type: {doc.metadata.get('symbol_type', '')}
Language: {doc.metadata.get('language', '')}
Lines: {doc.metadata['start_line']}-{doc.metadata['end_line']}
{doc.page_content}"""
                for doc in documents
            )

        rag_chain = (
            {
                "context": retriever | format_documents,
                "question": RunnablePassthrough()
            }
            | self.chain
        )

        return rag_chain