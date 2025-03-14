import boto3
import json
import logging
from botocore.exceptions import ClientError
from openai import OpenAI
import os
from langdetect import detect, LangDetectException

def get_openai_key():
    """Retrieve OpenAI API key from AWS Secrets Manager."""
    secret_name = "api_key_openai"
    region_name = "eu-central-1"
    
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        secrets = json.loads(response['SecretString'])
        return secrets.get('api_key')  # Assuming the key is stored under 'api_key' in the secret
    except ClientError as e:
        logging.error(f"Error retrieving secret: {e}")
        raise

def get_openai_client():
    """Get OpenAI client with API key from AWS Secrets Manager."""
    api_key = get_openai_key()
    return OpenAI(api_key=api_key)

def detect_language(text: str) -> str:
    """Detect the language of the input text."""
    try:
        lang = detect(text)
        lang_map = {
            'nl': 'Dutch',
            'de': 'German',
            'fr': 'French',
            'en': 'English',
            'es': 'Spanish'
        }
        return lang_map.get(lang, 'English')
    except LangDetectException:
        return 'English'

def translate_text(client, text: str, target_language: str = 'English') -> str:
    """Translate text to target language using GPT-4."""
    if not text or len(text.strip()) == 0:
        return text
        
    detected_lang = detect_language(text)
    if detected_lang == target_language:
        return text
        
    system_prompt = f"You are a translator. Translate the text to {target_language}, maintaining the same meaning and intent. Only respond with the translation, nothing else."
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content 