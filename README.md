# Trustoo Knowledge Base Search

A smart search system for Trustoo's internal knowledge base, powered by OpenAI's vector store technology. The system processes various document types (XLSX, DOCX) and provides accurate answers based on the content, with special handling for reclaim-related queries.

## Features

- Document Processing:
  - Excel (.xlsx) file processing with sheet preservation
  - Word (.docx) file processing
  - Automatic language detection and translation
- Smart Search:
  - Semantic search using OpenAI's vector store
  - Context-aware responses
  - Special handling for reclaim queries and exceptions
- Language Support:
  - Multi-language query support
  - Maintains company terminology (e.g., "reclaim" terms)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
OPENAI_API_KEY=your_api_key_here
```

3. Process documents:
```bash
python src/process_documents.py
```

4. Create vector store:
```bash
python src/create_vector_store.py
```

5. Run the search interface:
```bash
python src/search_knowledge.py
```

## Project Structure

```
trustoo-knowledge-base/
├── src/
│   ├── __init__.py
│   ├── process_documents.py
│   ├── create_vector_store.py
│   ├── search_knowledge.py
│   └── utils.py
├── tests/
│   └── __init__.py
├── docs/
│   └── README.md
├── .gitignore
├── requirements.txt
└── README.md
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Submit a pull request

## License

Proprietary - Trustoo B.V. 