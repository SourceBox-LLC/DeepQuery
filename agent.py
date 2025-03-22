# agent.py
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import os
import logging
import json
import re
from custom_tools import create_image_tool, code_interpreter
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.utilities.tavily_search import TavilySearchAPIWrapper
from langchain_community.tools.pubmed.tool import PubmedQueryRun

import streamlit as st
import boto3


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


logger.info(f"DEBUG TAVILY_API_KEY: {st.secrets['default']['TAVILY_API_KEY']}")


def initialize_agent(model_id):
    """Initialize and return a ReAct agent with Bedrock and Tavily search capabilities."""
    memory = MemorySaver()
    
    # Retrieve the TAVILY_API_KEY from secrets
    api_key = st.secrets['default'].get('TAVILY_API_KEY')
    if not api_key:
        logging.error("TAVILY_API_KEY is missing from the secrets.")
        st.error("Configuration Error: TAVILY_API_KEY is not set. Please contact the administrator.")
        return None
    else:
        logging.info("TAVILY_API_KEY successfully retrieved.")
        # Log the length to ensure it's not empty without exposing the key
        logging.info(f"TAVILY_API_KEY length: {len(api_key)}")
    
    # Set the API key as an environment variable (if required by the library)
    os.environ["TAVILY_API_KEY"] = api_key
    
    try:
        # Initialize Bedrock model
        logging.info("Initializing Bedrock model...")
        model = ChatBedrock(
            model=model_id,
            beta_use_converse_api=True,
            streaming=True,
            region_name=st.secrets["default"]["REGION"]
        )
        
        # Initialize Tavily search without passing api_key directly
        logging.info("Initializing Tavily search...")
        tavily_search = TavilySearchAPIWrapper()
        search = TavilySearchResults(api_wrapper=tavily_search)
        
        # Initialize PubMed search
        pubmed_search = PubmedQueryRun()
        
        # Create agent executor with tools
        logging.info("Creating agent executor...")
        agent_executor = create_react_agent(
            model,
            tools=[search, create_image_tool, code_interpreter, pubmed_search],
            checkpointer=memory
        )
        
        logging.info("Agent executor initialized successfully.")
        return agent_executor
    
    except Exception as e:
        logging.error(f"Failed to initialize agent: {e}", exc_info=True)
        st.error("An error occurred while initializing the agent.")
        return None


def query_agent(agent_executor, messages):
    """
    Query the agent with a list of messages and return the streamed response.
    Yields chunks of three possible types:
      - {"type": "response", "content": text}
      - {"type": "tool_log", "content": log_text}
      - {"type": "error", "content": error_message}
    """
    logger.info(f"Sending messages: {messages}")
    config = {"configurable": {"thread_id": "abc123"}}

    # Define a combined regex pattern to extract and remove both tool use logs and text logs
    log_pattern = re.compile(
        r"\{'type': 'tool_use', 'name': '([^']+)', 'input': \{'prompt': '([^']+)'\}, 'id': '([^']+)'\}"
        r"|\{'type': 'tool_use', 'name': '([^']+)', 'input': \{'query': '([^']+)'\}, 'id': '([^']+)'\}"
        r"|\{'type': 'text', 'text': \"[^\"]+\"\}"
    )

    try:
        for chunk in agent_executor.stream({"messages": messages}, config):
            # Check if we have messages in the chunk
            if "agent" in chunk and "messages" in chunk["agent"]:
                for message in chunk["agent"]["messages"]:
                    if hasattr(message, 'content'):
                        if isinstance(message.content, list):
                            # If content is a list, join its elements
                            content = " ".join(str(item) for item in message.content)
                        else:
                            # If content is a string, use it directly
                            content = str(message.content)
                        
                        # Use regex to find tool use logs in the response
                        tool_logs = log_pattern.findall(content)
                        for log in tool_logs:
                            if log[0] or log[3]:  # Only yield tool logs, not text logs
                                tool_log_content = f"Tool Name: {log[0] or log[3]}, Query/Prompt: {log[1] or log[4]}, ID: {log[2] or log[5]}"
                                yield {"type": "tool_log", "content": tool_log_content}
                        
                        # Remove all logs from the content
                        content = log_pattern.sub('', content).strip()

                        # Only yield non-log text content
                        if content:
                            yield {"type": "response", "content": content}

    except Exception as e:
        logger.error(f"Error during agent query: {e}", exc_info=True)
        yield {"type": "error", "content": f"An error occurred: {e}"}