from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
import os
import logging

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
    Query the agent with a specific question and stream the response.
    """
    logger.info(f"Sending query: {query}")
    config = {"configurable": {"thread_id": "abc123"}}
    
    # Use the stream method to get chunks of the response
    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=query)]},
        config
    ):
        # Check if we have messages in the chunk
        if "agent" in chunk and "messages" in chunk["agent"]:
            for message in chunk["agent"]["messages"]:
                if hasattr(message, 'content') and message.content:
                    print(message.content, end="", flush=True)

# Example usage
if __name__ == "__main__":
    try:
        logger.info("Starting agent initialization...")
        agent = initialize_agent()
        logger.info("Agent initialized successfully.")
        
        print("\nAsking about Bitcoin price...\n")
        query_agent(agent, "what was the price of bitcoin last week?")
        print("\n")  # Add a newline at the end
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
