import openai
import hashlib
import os
import json

class Cache:
    def __init__(self, cache_file="_/translations_cache.json"):
        """
        Initialize the Cache object with a specified cache file.

        This constructor sets the cache file path and loads existing cache data
        from the file if it exists. If the cache file does not exist, an empty
        cache is initialized.
        """
        self.cache_file = cache_file
        self.cache = self.load_cache()

    def load_cache(self):
        """
        Load the cache from the specified cache file.

        This function checks if the cache file exists. If it does, it reads the
        contents of the file and returns it as a dictionary. If the file does
        not exist, it returns an empty dictionary, indicating that there are
        no cached translations available.
        """
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_cache(self):
        """
        Save the current cache data to the specified cache file.

        This function writes the cache dictionary to the file in JSON format.
        It ensures that non-ASCII characters are preserved and the output is
        formatted with indentation for better readability. This is called
        whenever the cache is updated to ensure that the latest translations
        are stored persistently.
        """
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=4)

    def get(self, text, target_language):
        """
        Retrieve a translation from the cache using a unique key generated
        from the text and target language.

        This function generates a unique key by hashing the combination of
        the text and target language. It checks the cache for this key and
        returns the corresponding translation if it exists. If the key is
        not found, it returns None, indicating that the translation is not
        cached.
        """
        key = hashlib.md5(f"{text}_{target_language}".encode('utf-8')).hexdigest()
        return self.cache.get(key)

    def set(self, text, target_language, translation):
        """
        Store a new translation in the cache.

        This function generates a unique key for the translation by hashing
        the combination of the text and target language. It then saves the
        translation in the cache dictionary under this key. After updating
        the cache, it calls the save_cache method to persist the changes
        to the cache file.
        """
        key = hashlib.md5(f"{text}_{target_language}".encode('utf-8')).hexdigest()
        self.cache[key] = translation
        self.save_cache()

class Translator:
    def __init__(self, api_key):
        """
        Initialize the Translator object with the provided OpenAI API key.

        This constructor sets up the OpenAI client instance using the provided
        API key, allowing the Translator class to make requests to the OpenAI
        API for translation services.
        """
        self.client = openai.OpenAI(api_key=api_key)

    def translate(self, text, target_language, strict_words=None, use_cache=False, cache_file="_/translations_cache.json", additional_prompt=None):
        """
        Translate the given text into the specified target language.

        This function handles the translation process, optionally using a cache
        to store and retrieve translations. It constructs a system prompt for
        the translation request, including any strict word translations and
        additional instructions. If caching is enabled, it checks for an existing
        translation before making a request to the OpenAI API. After receiving
        the response, it processes the translation and caches it if required.

        Parameters:
        - text: The text to be translated.
        - target_language: The language to translate the text into.
        - strict_words: A dictionary of words that require specific translations.
        - use_cache: A boolean indicating whether to use caching.
        - cache_file: The path to the cache file.
        - additional_prompt: Any additional instructions for the translation.

        Returns:
        - The translated text as a string.
        """
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
