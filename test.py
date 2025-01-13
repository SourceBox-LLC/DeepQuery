import replicate
import logging
import streamlit as st

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Replicate client using secrets
def initialize_replicate_client():
    api_token = "r8_DshRgfcAfXQl3VL9D4KTLwX5hFQfkLE1XuGKc"
    return replicate.Client(api_token=api_token)

replicate_client = initialize_replicate_client()

def call_sana(prompt, replicate_client, width, height, model_variant, guidance_scale, num_inference_steps):
    """
    Generates an image using the Flux Pro model on Replicate.

    Args:
        prompt (str): The prompt for image generation.
        replicate_client (replicate.Client): Initialized Replicate client.
        width (int): Width of the generated image.
        height (int): Height of the generated image.
        model_variant (str): Model variant to use.
        guidance_scale (int): Guidance scale parameter.
        num_inference_steps (int): Number of inference steps.

    Returns:
        str: URL of the generated image or None if failed.
    """
    try:
        logging.info("Generating image with prompt: %s", prompt)
        output = replicate_client.run(
            "nvidia/sana:c6b5d2b7459910fec94432e9e1203c3cdce92d6db20f714f1355747990b52fa6",
            input={
                "width": width,
                "height": height,
                "prompt": prompt,
                "model_variant": model_variant,
                "guidance_scale": guidance_scale,
                "negative_prompt": "",
                "pag_guidance_scale": 2,
                "num_inference_steps": num_inference_steps
            }
        )
        logging.info("Image generation successful. Output: %s", output)
        return output  # Assuming output is a URL to the image
    except Exception as e:
        logger.error(f"Error generating image with Flux Pro: {e}")
        return None

if __name__ == "__main__":  
    output = call_sana(
        "a cyberpunk cat with a neon sign that says \"Sana\"",
        replicate_client,
        width=1600,
        height=1024,
        model_variant="1600M-1024px",
        guidance_scale=5,
        num_inference_steps=18
    )
    print(output)
