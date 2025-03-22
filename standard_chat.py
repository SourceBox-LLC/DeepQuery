from langchain.chains import LLMChain
from langchain_community.llms import Replicate
from langchain_core.prompts import PromptTemplate
import os
import streamlit as st

# Use the API token from the default section of Streamlit secrets
os.environ["REPLICATE_API_TOKEN"] = st.secrets["default"]["REPLICATE_API_TOKEN"]

def query_chat(query, model_id):
    llm = Replicate(
        model=model_id,
        model_kwargs={"temperature": 0.75, "max_length": 500, "top_p": 1},
    )
    prompt = f"""
    User: {query}
    Assistant:
    """
    call_llm = llm.invoke(prompt)
    return call_llm


if __name__ == "__main__":
    print(query_chat("Can a dog drive a car?", "meta/meta-llama-3-8b-instruct"))
