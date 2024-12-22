# agent.py
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
import os
import logging
import json
from tools import create_image_tool

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
    
    logger.info("Creating agent...")
    agent_executor = create_react_agent(model, [search, create_image_tool], checkpointer=memory)
    
    return agent_executor

def query_agent(agent_executor, messages):
    """
    Query the agent with a list of messages and return the streamed response.
    """
    logger.info(f"Sending messages: {messages}")
    config = {"configurable": {"thread_id": "abc123"}}
    
    response_content = ""  # To accumulate the response content

    try:
        for chunk in agent_executor.stream(
            {"messages": messages},
            config
        ):
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
                        
                        response_content += content
                        yield content  # Yield each chunk for streaming

    except Exception as e:
        logger.error(f"Error during agent query: {e}", exc_info=True)
        yield f"An error occurred: {e}"

