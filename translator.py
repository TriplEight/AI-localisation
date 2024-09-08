import openai
import hashlib
import os
import json

class Cache:
    def __init__(self, cache_file="translations_cache.json"):
        self.cache_file = cache_file
        self.cache = self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=4)

    def get(self, text, target_language):
        key = hashlib.md5(f"{text}_{target_language}".encode('utf-8')).hexdigest()
        return self.cache.get(key)

    def set(self, text, target_language, translation):
        key = hashlib.md5(f"{text}_{target_language}".encode('utf-8')).hexdigest()
        self.cache[key] = translation
        self.save_cache()

class Translator:
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)

    def translate(self, text, target_language, strict_words=None, use_cache=False, cache_file="translations_cache.json", additional_prompt=None):
        strict_words = strict_words or {}
        cache = Cache(cache_file) if use_cache else None

        # Check if the translation is in cache
        if use_cache:
            cached_translation = cache.get(text, target_language)
            if cached_translation:
                return cached_translation

        # Prepare the translation prompt with strict words
        strict_words_prompt = ', '.join([f"'{word}': '{translation}'" for word, translation in strict_words.items()])
        
        # Modify the system prompt to prevent unnecessary texts
        system_prompt = (
            f"Translate the following text to {target_language}, ensuring the translation is exact and concise. "
            f"Only provide the translated text, without any explanations, introductions, or additional phrases. "
            f"Use the following translations for specific words: {strict_words_prompt}."
        )

        if additional_prompt:
            system_prompt += f" {additional_prompt}"

        user_prompt = f"Text: {text}\n\nTranslated Text:"

        # Call the OpenAI API using the modern model (e.g., gpt-4)
        response = self.client.chat.completions.create(
            model="gpt-4o",  # Updated to use GPT-4 model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        # Strip any unnecessary leading "Text:" or similar artifacts
        translation = response.choices[0].message.content.strip()
        if translation.lower().startswith("text:"):
            translation = translation[len("text:"):].strip()

        # Cache the translation if caching is enabled
        if use_cache:
            cache.set(text, target_language, translation)

        return translation