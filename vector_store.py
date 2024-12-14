import logging
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_aws.embeddings.bedrock import BedrockEmbeddings
from langchain_core.documents import Document

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_vector_store():
    """Initialize and return an InMemoryVectorStore with Bedrock embeddings."""
    logging.info("Initializing Bedrock embeddings.")
    embeddings = BedrockEmbeddings(
        model_id='amazon.titan-embed-text-v1',
        region_name='us-east-1',  # Specify your AWS region
    )
    logging.info("Creating InMemoryVectorStore.")
    return InMemoryVectorStore(embeddings)

def add_documents_to_store(vector_store, file_contents):
    """
    Add documents to the vector store from file contents.
    
    :param vector_store: The vector store to add documents to.
    :param file_contents: A list of tuples, each containing (file_id, content, metadata).
    """
    logging.info("Adding documents to the vector store.")
    documents = [
        Document(id=file_id, page_content=content, metadata=metadata)
        for file_id, content, metadata in file_contents
    ]
    vector_store.add_documents(documents=documents)
    logging.info("Documents added successfully.")

def search_documents(vector_store, query, k=1):
    """Search for documents similar to the query."""
    logging.info(f"Performing similarity search for query: {query}")
    results = vector_store.similarity_search(query=query, k=k)
    logging.info(f"Search completed. Found {len(results)} results.")
    return results

if __name__ == "__main__":
    # Example usage
    vector_store = create_vector_store()
    
    # Example file contents
    file_contents = [
        ("1", "This is the content of file 1.", {"type": "text"}),
        ("2", "This is the content of file 2.", {"type": "text"})
    ]
    
    # Add documents to the store
    add_documents_to_store(vector_store, file_contents)
    
    # Perform a search
    query = "content of file"
    results = search_documents(vector_store, query)
    
    # Print search results
    for doc in results:
        print(f"Found document: {doc.page_content} with metadata: {doc.metadata}")
