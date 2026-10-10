from langchain_core.messages import HumanMessage, ToolMessage
from app.tools import search_repository, read_repository_file
from dotenv import load_dotenv

load_dotenv()
class RepoPilotToolAgent:
    def __init__(self, llm):
        self.tools = [
            search_repository,
            read_repository_file
        ]

        self.tool_map = {
            tool.name: tool
            for tool in self.tools
        }

        self.llm = llm.bind_tools(self.tools)

    def run(self, question, repository_name, repository_path):
        messages = [HumanMessage(content=question)]

        while True:
            response = self.llm.invoke(messages)

            messages.append(response)

            if not response.tool_calls:
                return response.content

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                tool_args["repository_name"] = repository_name
                tool_args["repository_path"] = repository_path

                tool = self.tool_map[tool_name]

                result = tool.invoke(tool_args)

                messages.append(
                    ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"]
                    )
                )