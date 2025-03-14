import json
import re
from utils import get_openai_client, detect_language, translate_text

def load_vector_store_id():
    """Load the vector store ID from file."""
    with open("vector_store_id.txt", "r") as f:
        return f.read().strip()

def adjust_score_by_source(score: float, source: str, content_str: str = None, is_reclaim_query: bool = False) -> float:
    """Adjust the relevance score based on the source folder and content."""
    # For reclaim queries, ONLY use documents, completely ignore Slack messages
    if is_reclaim_query:
        # Check if it's from processed_documents.json (these have no thread_ts)
        if '"thread_ts":' in str(content_str):
            return 0.0  # Ignore Slack messages for reclaim queries
        else:
            return score * 2.0  # Boost document sources
    
    # For non-reclaim queries, use normal source multipliers
    source_multipliers = {
        "official_document": 2.0,
        "product-changes": 1.75,
        "help": 1.25,
        "customer-success": 1.0
    }
    
    # Get base score from source
    return score * source_multipliers.get(source, 1.0)

def extract_metadata(content_str: str):
    """Extract metadata from content string."""
    source = None
    document_name = None
    
    # First try to extract from JSON metadata
    try:
        metadata_match = re.search(r'"metadata":\s*({[^}]+})', content_str)
        if metadata_match:
            metadata = json.loads(metadata_match.group(1))
            source = metadata.get("source")
            document_name = metadata.get("file_name")
            
            # If no document name but we have content from a file
            if not document_name and "file_path" in metadata:
                document_name = metadata["file_path"].split("/")[-1]
    except:
        pass
    
    # If still no document name but content looks like it's from a document
    if not document_name and not source:
        # Look for common document indicators
        if "Reclaim Guideline" in content_str:
            document_name = "Reclaim Guideline 2025.xlsx"
            source = "official_document"
        elif "Customer Success Manual" in content_str:
            document_name = "Customer Success Manual.docx"
            source = "official_document"
    
    # If no source found in metadata, try to detect from content
    if not source:
        if "product-changes" in content_str:
            source = "product-changes"
        elif "help" in content_str:
            source = "help"
        elif "customer-success" in content_str:
            source = "customer-success"
    
    return source, document_name

def generate_slack_link(thread_ts: str, source: str) -> str:
    """Generate a Slack message link from thread timestamp and source."""
    channel_map = {
        "product-changes": "product-changes",
        "help": "help",
        "customer-success": "customer-success"
    }
    
    channel = channel_map.get(source, "")
    if thread_ts and channel:
        return f"https://trustooworkspace.slack.com/archives/{channel}/p{thread_ts.replace('.', '')}"
    return None

def search_and_respond(client, vector_store_id: str, query: str):
    """Search the vector store and generate a response."""
    # 1. Detect query language and translate to English if needed
    query_language = detect_language(query)
    search_query = query if query_language == 'English' else translate_text(client, query)
    
    # 2. Create a more focused search query based on the context
    query_context = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are a search query analyzer. Analyze the query and return ONLY a JSON object with exactly these fields:
{
    "main_concept": "the primary concept being asked about",
    "search_query": "the enhanced search query to find relevant information",
    "exclude_terms": ["terms", "that", "should", "reduce", "relevance"],
    "is_reclaim_query": false
}

Your task:
1. For reclaim/dispute/chargeback queries:
   - Set is_reclaim_query to true
   - Focus search_query on finding official guidelines and exceptions
   - Include terms like "guideline", "exception", "rule", "policy"
   - For profession/role-specific queries (e.g. DJs, vloerleggers, mediators):
     * Include both the profession name and "general exceptions"
     * Keep profession names in original language (don't translate)
2. For other queries:
   - Keep search focused on the specific topic
   - Include synonyms and related terms
3. Always identify terms that could lead to irrelevant results in exclude_terms

Example for reclaim query "what are exceptions for vloerleggers?":
{
    "main_concept": "vloerleggers reclaim exceptions",
    "search_query": "vloerleggers general exceptions reclaim guideline materiaal gekocht",
    "exclude_terms": ["review", "profile"],
    "is_reclaim_query": true
}

IMPORTANT: Return ONLY the JSON object, no other text."""
            },
            {
                "role": "user",
                "content": f"Analyze this query: {search_query}"
            }
        ]
    )
    
    try:
        query_analysis = json.loads(query_context.choices[0].message.content)
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails
        query_analysis = {
            "main_concept": search_query,
            "search_query": search_query,
            "exclude_terms": [],
            "is_reclaim_query": "reclaim" in search_query.lower() or "dispute" in search_query.lower() or "chargeback" in search_query.lower()
        }
    
    # 3. Search vector store with enhanced query
    search_response = client.vector_stores.search(
        vector_store_id=vector_store_id,
        query=query_analysis["search_query"],
        max_num_results=30
    )
    
    # 4. Process and boost search results
    context = []
    exclude_terms = query_analysis.get("exclude_terms", [])
    is_reclaim_query = query_analysis.get("is_reclaim_query", False)
    
    for result in search_response.data:
        content_str = str(result.content)
        base_score = float(result.score)
        
        # Boost score for content containing requirement/criteria terms
        requirement_indicators = ["need", "require", "must have", "rules", "criteria", "only if", "mandatory"]
        if any(term in content_str.lower() for term in requirement_indicators):
            base_score *= 1.5
        
        # Extra boost for messages that look like lists
        if any(marker in content_str for marker in ["1:", "2:", "3:", "4:", ":heavy_check_mark:", "✓", "•", "-"]):
            base_score *= 1.5
        
        # Reduce score if content contains excluded terms
        if exclude_terms and any(term.lower() in content_str.lower() for term in exclude_terms):
            base_score *= 0.3
        
        # Extract metadata
        source, document_name = extract_metadata(content_str)
        thread_ts = re.search(r'"thread_ts":\s*"([^"]+)"', content_str)
        thread_ts = thread_ts.group(1) if thread_ts else None
        slack_link = generate_slack_link(thread_ts, source) if thread_ts else None
        
        # Create context entry with boosted score
        entry = {
            "content": content_str,
            "score": adjust_score_by_source(base_score, source, content_str, is_reclaim_query),
            "source": source,
        }
        
        if slack_link:
            entry["slack_link"] = slack_link
        if document_name:
            entry["document_name"] = document_name
        
        # Only append if score is not zero
        if entry["score"] > 0:
            context.append(entry)
    
    # Sort by adjusted score and take top 8 instead of 5
    context.sort(key=lambda x: x["score"], reverse=True)
    context = context[:8]
    
    # 5. Generate response in English
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": f"""You are a helpful customer success assistant. Answer questions accurately and professionally.

Topic: {query_analysis["main_concept"]}

Guidelines:
- Focus on information directly relevant to the question asked
- Keep different concepts separate and distinct
- If listing requirements or steps, use a clear numbered list
- Each item should be complete and on its own line
- Double-check that all numbered items are present and properly formatted
- For document sources, cite as [Document: filename]
- For Slack messages, use [Source](link) format
- Always include the source of information
- Keep responses clear and concise

Language and Terminology Guidelines:
- ALWAYS use these exact terms regardless of response language:
  - "reclaim" (noun) or "reclaiming" (verb) or "reclameren" (Dutch verb)
  - Never translate these to other terms like "herroeping", "terugvordering", etc.
- Keep all technical terms in English:
  - "budget", "mediator", "DJ", etc.
  - Document names and system terms
- This applies to ALL languages - these are company standard terms

When answering reclaim exception queries:
- ALWAYS start with the specific exception if found
- If a specific exception exists, quote it exactly as written
- If NO specific exception is found, cite the general rule:
  "If you can't find the exception you are looking for - it's not an exception! And therefore needs to be denied"
- Be explicit about whether exceptions are allowed or not
- Always cite the source document

Other guidelines:
- Stay focused on the specific concept being asked about
- Do not mix information about different features or concepts
- If answering whether something is allowed/valid, clearly state yes/no and explain why
- Prioritize explicit statements and lists from official documents"""
            },
            {
                "role": "user",
                "content": f"""Question: {search_query}

Sources:
{json.dumps([{
    "content": c["content"],
    "source": c.get("slack_link", c["source"]),
    "document_name": c.get("document_name", "Unknown Document")
} for c in context], indent=2)}

Based on these sources, please provide a clear and specific answer to the question. For document sources, cite them as [Document: filename]. IMPORTANT: Always use the term 'reclaim' or 'reclameren' regardless of the response language - these are company standard terms."""
            }
        ]
    )
    
    english_response = response.choices[0].message.content
    
    # 6. Translate response back to original language if needed
    return english_response if query_language == 'English' else translate_text(client, english_response, query_language)

def main():
    client = get_openai_client()
    vector_store_id = load_vector_store_id()
    
    print("Customer Success Knowledge Base Search")
    print("=====================================")
    print("Type 'quit' to exit")
    print()
    
    while True:
        query = input("What would you like to know? ")
        if query.lower() == 'quit':
            break
        
        try:
            response = search_and_respond(client, vector_store_id, query)
            print("\nResponse:")
            print("---------")
            print(response)
            print("\n")
        except Exception as e:
            print(f"Error: {str(e)}")
            print("Full error details:", e)
            import traceback
            print("Traceback:", traceback.format_exc())

if __name__ == "__main__":
    main() 