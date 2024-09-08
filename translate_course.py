import os
import logging
from git import Repo
from translator import Translator
import json

# Configuring logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load strict words from a JSON file
def load_strict_words(file_path="strict_words.json"):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def get_changed_files(commit_hash):
    logging.info(f"Getting changed files for commit: {commit_hash}")
    try:
        repo = Repo(".")  # Use the current directory as the repository path
        commit = repo.commit(commit_hash)
        changes = commit.stats.files
        logging.info(f"Changed files: {list(changes.keys())}")
        return changes
    except Exception as e:
        logging.exception(f"Exception occurred while getting changed files: {e}")
        return {}

def process_files(changes, target_language, translator, strict_words):
    for file_path, stats in changes.items():
        logging.info(f"Processing file: {file_path}")
        
        if not file_path.startswith('ru/'):
            continue

        new_file_path = file_path.replace('ru/', f'{target_language}/')

        if file_path.endswith('.md'):
            translate_markdown(file_path, new_file_path, target_language, translator, strict_words)
        else:
            copy_file(file_path, new_file_path)

def translate_markdown(file_path, new_file_path, target_language, translator, strict_words):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        logging.debug(f"Original content (first 100 chars): {content[:100]}...")

        # Add the additional prompt about Markdown and frontmatter
        additional_prompt = (
            "The provided text is a Markdown document. "
            "It's important to preserve the formatting, including headers, lists, and code blocks. "
            "There is a frontmatter section at the beginning of the document (between '---' markers). "
            "Translate only the values in the frontmatter, not the keys."
        )

        # Using the translator with caching enabled and specifying the cache file
        translated_content = translator.translate(
            content, target_language, strict_words=strict_words, use_cache=True, cache_file="md_cache.json", additional_prompt=additional_prompt
        )

        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)

        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)

        logging.info(f"Translated {file_path} -> {new_file_path}")
    except Exception as e:
        logging.exception(f"Exception occurred while translating file {file_path}: {e}")

def copy_file(file_path, new_file_path):
    try:
        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
        with open(file_path, 'rb') as src_file:
            with open(new_file_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
        logging.info(f"Copied {file_path} -> {new_file_path}")
    except Exception as e:
        logging.exception(f"Exception occurred while copying file {file_path}: {e}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        target_language = sys.argv[1]
        commit_hash = None  # Process all files if no commit hash is provided
    elif len(sys.argv) == 3:
        target_language = sys.argv[1]
        commit_hash = sys.argv[2]
    else:
        logging.error("Usage: python script.py <target_language> [commit_hash]")
        sys.exit(1)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.critical("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    translator = Translator(api_key)

    # Load the strict words
    strict_words = load_strict_words()

    if commit_hash:
        changed_files = get_changed_files(commit_hash)
    else:
        changed_files = {os.path.join(root, file): None for root, dirs, files in os.walk('ru') for file in files}

    if not changed_files:
        logging.warning("No files to process.")
        sys.exit(0)

    process_files(changed_files, target_language, translator, strict_words)