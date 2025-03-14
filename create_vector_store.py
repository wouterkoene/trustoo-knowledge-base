import json
import os
from utils import get_openai_client

def load_processed_data():
    """Load both processed conversations and documents."""
    data = []
    
    # Load conversations if they exist
    if os.path.exists("processed_conversations.json"):
        with open("processed_conversations.json", 'r', encoding='utf-8') as f:
            data.extend(json.load(f))
    
    # Load documents if they exist
    if os.path.exists("processed_documents.json"):
        with open("processed_documents.json", 'r', encoding='utf-8') as f:
            data.extend(json.load(f))
    
    return data

def create_vector_store(client, name: str = "customer-success-knowledge"):
    """Create a new vector store."""
    # Create the vector store
    vector_store = client.vector_stores.create(
        name=name,
        metadata={
            "description": "Customer Success knowledge base from Slack conversations and documents",
            "source": "slack_export_and_documents",
            "type": "customer_support"
        }
    )
    return vector_store

def upload_data_to_store(client, vector_store_id: str, data):
    """Upload data to the vector store."""
    # First, create a temporary file with the content
    temp_file = "temp_content.json"
    
    # Format as a proper JSON array
    content = []
    for item in data:
        content.append({
            "text": item["content"],
            "metadata": item["metadata"]
        })
    
    # Write as a proper JSON file
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    
    # Upload the file to OpenAI
    with open(temp_file, "rb") as f:
        file = client.files.create(
            file=f,
            purpose="assistants"
        )
    
    # Create a file batch for the vector store
    batch = client.vector_stores.file_batches.create(
        vector_store_id=vector_store_id,
        file_ids=[file.id]
    )
    
    # Clean up the temporary file
    os.remove(temp_file)
    
    return batch

def main():
    # Initialize OpenAI client
    client = get_openai_client()
    
    # Load all processed data
    data = load_processed_data()
    print(f"Loaded {len(data)} items")
    
    # Create vector store
    vector_store = create_vector_store(client)
    print(f"Created vector store with ID: {vector_store.id}")
    
    # Upload data
    batch = upload_data_to_store(client, vector_store.id, data)
    print(f"Created file batch with ID: {batch.id}")
    
    # Save vector store ID for later use
    with open("vector_store_id.txt", "w") as f:
        f.write(vector_store.id)
    print("Vector store ID saved to vector_store_id.txt")

if __name__ == "__main__":
    main() 