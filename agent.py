# agent.py
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from dotenv import load_dotenv
import os
import logging
import json
import re

from custom_tools import create_image_tool, code_interpreter
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools.pubmed.tool import PubmedQueryRun


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_agent(model_id):
    """Initialize and return a ReAct agent with Bedrock and Tavily search capabilities."""
    load_dotenv()
    memory = MemorySaver()
    
    logger.info("Initializing Bedrock model...")
    model = ChatBedrock(
        model=model_id,
        beta_use_converse_api=True,
        streaming=True
    )
    
    logger.info("Initializing Tavily search...")
    search = TavilySearchResults(
        max_results=2, 
        api_key=os.getenv("TAVILY_API_KEY")
    )

    pubmed_search = PubmedQueryRun()
    
    logger.info("Creating agent...")
    agent_executor = create_react_agent(
        model,
        tools=[search, create_image_tool, code_interpreter, pubmed_search],
        checkpointer=memory
    )
    
    return agent_executor


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

    # Define regex pattern to extract tool use logs
    tool_use_pattern = re.compile(r"\{'type': 'tool_use', 'name': '([^']+)', 'input': \{'query': '([^']+)'\}, 'id': '([^']+)'\}")

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
                        
                        # Check if the message is a tool usage log
                        if message.type == "tool_use":
                            yield {"type": "tool_log", "content": content}
                        else:
                            # Use regex to find tool use logs in the response
                            tool_logs = tool_use_pattern.findall(content)
                            for log in tool_logs:
                                tool_log_content = f"Tool Name: {log[0]}, Query: {log[1]}, ID: {log[2]}"
                                yield {"type": "tool_log", "content": tool_log_content}
                            
                            yield {"type": "response", "content": content}

    except Exception as e:
        logger.error(f"Error during agent query: {e}", exc_info=True)
        yield {"type": "error", "content": f"An error occurred: {e}"}
