import replicate
from langchain_core.tools import tool
from dotenv import load_dotenv
import os

load_dotenv()

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

if __name__ == "__main__":
    result = create_image_tool("a majestic snow-capped mountain peak")
    print(result)
