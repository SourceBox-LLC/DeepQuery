from langchain_core.tools import Tool
from langchain_experimental.utilities import PythonREPL

@tool
def code_interpreter(code: str):
    python_repl = PythonREPL()
    # You can create the tool to pass to an agent
    repl_tool = Tool(
        name="python_repl",
        description="A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`.",
        func=python_repl.run,
    )

    return python_repl.run(code)