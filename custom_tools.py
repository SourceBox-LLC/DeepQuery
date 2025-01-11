import replicate
from langchain_core.tools import tool
from langchain_core.tools import Tool
from langchain_experimental.utilities import PythonREPL
import os
import requests
import base64
from io import BytesIO
import base64
import pandas as pd
import io
import streamlit as st
from langchain.tools import tool



@tool("create_image")
def create_image_tool(prompt: str) -> str:
    """Use this tool to generate an image from a text description.
    
    Args:
        prompt (str): The description of the image you want to generate
        
    Returns:
        str: The direct URL of the generated image
        
    Example:
        Input: "a red apple on a white table"
        Output: https://replicate.delivery/pbxt/example123/image.jpg
    
    Note: Return ONLY the URL, no other text or description.
    """
    output = replicate.run(
        "black-forest-labs/flux-1.1-pro-ultra",
        input={
            "raw": False,
            "prompt": prompt,
            "aspect_ratio": "3:2",
            "output_format": "jpg",
            "safety_tolerance": 2,
            "image_prompt_strength": 0.1
        }
    )
    
    return output

@tool
def code_interpreter(code: str) -> str:
    """Execute Python code in a secure environment.
    
    Args:
        code (str): The Python code to execute
        
    Returns:
        str: The output of the executed code
        
    Example:
        Input: "print('Hello, World!')"
        Output: Hello, World!
        
    Note: Only prints and returned values will be visible in the output.
    """
    python_repl = PythonREPL()
    repl_tool = Tool(
        name="python_repl",
        description="A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`.",
        func=python_repl.run,
    )

    return python_repl.run(code)



if __name__ == "__main__":
    result = create_image_tool("a majestic snow-capped mountain peak")
    print(result)
