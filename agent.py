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
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_agent():
    """Initialize and return a ReAct agent with Bedrock and Tavily search capabilities."""
    load_dotenv()
    memory = MemorySaver()
    
    logger.info("Initializing Bedrock model...")
    model = ChatBedrock(
        model="anthropic.claude-3-5-sonnet-20240620-v1:0",
        beta_use_converse_api=True,
        streaming=True
    )
    
    logger.info("Initializing Tavily search...")
    search = TavilySearchResults(
        max_results=2, 
        api_key=os.getenv("TAVILY_API_KEY")
    )
    
    logger.info("Creating agent...")
    agent_executor = create_react_agent(model, [search], checkpointer=memory)
    
    return agent_executor

def query_agent(agent_executor, query):
    """
    Query the agent with a specific question and return the streamed response.
    """
    logger.info(f"Sending query: {query}")
    config = {"configurable": {"thread_id": "abc123"}}
    
    response_content = ""  # To accumulate the response content
    
    try:
        for chunk in agent_executor.stream(
            {"messages": [HumanMessage(content=query)]},
            config
        ):
            # Check if we have messages in the chunk
            if "agent" in chunk and "messages" in chunk["agent"]:
                for message in chunk["agent"]["messages"]:
                    if hasattr(message, 'content') and message.content:
                        # Check if the content is a string, if not, convert it to a string
                        if isinstance(message.content, str):
                            response_content += message.content
                            yield message.content  # Yield each chunk for streaming
                        else:
                            # Convert non-string content to a readable string
                            formatted_content = json.dumps(message.content, indent=2) if isinstance(message.content, (dict, list)) else str(message.content)
                            response_content += formatted_content
                            yield formatted_content  # Yield the formatted content
    except Exception as e:
        logger.error(f"Error during agent query: {e}", exc_info=True)
        yield f"An error occurred: {e}"

