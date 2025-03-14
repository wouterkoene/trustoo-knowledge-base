import json
import os
from datetime import datetime
from typing import List, Dict, Any
from utils import get_openai_client, detect_language, translate_text

def load_json_file(file_path: str) -> List[Dict[Any, Any]]:
    """Load and parse a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def process_message(message: Dict[Any, Any], client) -> Dict[str, Any]:
    """Process a single Slack message, translating if needed."""
    if not message.get('text'):
        return None
        
    # Extract basic message content
    content = message['text']
    
    # Detect and translate content if not in English
    detected_lang = detect_language(content)
    if detected_lang != 'English':
        content = translate_text(client, content)
    
    # Create processed message
    processed_message = {
        "content": content,
        "metadata": {
            "channel": message.get('channel', ''),
            "timestamp": message.get('ts', ''),
            "thread_ts": message.get('thread_ts', message.get('ts', '')),
            "user": message.get('user', ''),
            "original_language": detected_lang
        }
    }
    
    # Add source based on channel
    if 'product-changes' in message.get('channel', ''):
        processed_message['metadata']['source'] = 'product-changes'
    elif 'help' in message.get('channel', ''):
        processed_message['metadata']['source'] = 'help'
    elif 'customer-success' in message.get('channel', ''):
        processed_message['metadata']['source'] = 'customer-success'
    
    return processed_message

def group_messages_by_thread(messages: List[Dict[Any, Any]]) -> List[Dict[str, Any]]:
    """Group messages by their thread to create conversation contexts."""
    threads = {}
    
    for msg in messages:
        processed = process_message(msg, get_openai_client())
        thread_ts = processed['metadata']['thread_ts']
        
        if thread_ts not in threads:
            threads[thread_ts] = {
                'thread_ts': thread_ts,
                'messages': [],
                'timestamp': processed['metadata']['timestamp'],
                'participants': set()
            }
        
        threads[thread_ts]['messages'].append(processed)
        threads[thread_ts]['participants'].add(processed['metadata']['user'])
    
    # Convert threads to a list and format for vector store
    return [{
        'content': '\n'.join([f"{m['metadata']['user']}: {m['content']}" for m in thread['messages']]),
        'metadata': {
            'thread_ts': thread['thread_ts'],
            'timestamp': thread['timestamp'],
            'participants': list(thread['participants']),
            'message_count': len(thread['messages']),
            'source': thread['metadata']['source']
        }
    } for thread in threads.values()]

def process_directory(directory_path: str) -> List[Dict[str, Any]]:
    """Process all JSON files in the directory."""
    all_threads = []
    
    for filename in os.listdir(directory_path):
        if filename.endswith('.json') and filename != 'canvas_in_the_conversation.json':
            file_path = os.path.join(directory_path, filename)
            try:
                messages = load_json_file(file_path)
                threads = group_messages_by_thread(messages)
                # Add source information to metadata
                for thread in threads:
                    thread['metadata']['source'] = directory_path
                all_threads.extend(threads)
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
    
    return all_threads

def process_conversations(conversations: list) -> list:
    """Process all conversations, translating non-English content."""
    client = get_openai_client()
    processed_messages = []
    
    for conv in conversations:
        if not isinstance(conv, dict):
            continue
            
        processed = process_message(conv, client)
        if processed:
            processed_messages.append(processed)
    
    return processed_messages

def main():
    # Load conversations from JSON files
    conversations = []
    
    # Process files from different channels
    channels = ['product-changes', 'help', 'customer-success']
    for channel in channels:
        channel_dir = os.path.join(os.getcwd(), channel)
        if not os.path.exists(channel_dir):
            print(f"Directory not found: {channel}")
            continue
            
        for filename in os.listdir(channel_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(channel_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        channel_data = json.load(f)
                        for message in channel_data:
                            if isinstance(message, dict):
                                message['channel'] = channel
                        conversations.extend(channel_data)
                except Exception as e:
                    print(f"Error processing {file_path}: {str(e)}")
    
    # Process all conversations
    processed_conversations = process_conversations(conversations)
    
    # Save processed conversations
    output_file = "processed_conversations.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_conversations, f, ensure_ascii=False, indent=2)
    
    print(f"Processed {len(processed_conversations)} messages")
    print(f"Output saved to {output_file}")

if __name__ == "__main__":
    main() 