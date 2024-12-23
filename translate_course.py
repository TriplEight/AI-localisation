import os
import logging
from git import Repo
from translator import Translator
import json

# Configuring logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format='%(asctime)s - %(levelname)s - %(message)s')

def load_strict_words(file_path="_/strict_words.json"):
    """
    Loads a dictionary of strict words from a JSON file that should not be translated
    or require specific translation rules.

    Args:
        file_path (str): Path to the JSON file containing strict words

    Returns:
        dict: Dictionary of strict words and their translations/rules.
              Returns empty dict if file doesn't exist
    """
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def get_changed_files(commit_hash):
    """
    Retrieves a list of files that were modified in a specific git commit.

    Args:
        commit_hash (str): The git commit hash to analyze

    Returns:
        dict: Dictionary of changed files and their stats from the commit.
             Returns empty dict if there's an error

    Note:
        Uses the current directory as the git repository path
    """
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
    """
    Processes each changed file for translation or copying.

    Args:
        changes (dict): Dictionary of files to process and their stats
        target_language (str): Target language code for translation
        translator (Translator): Translator instance to use
        strict_words (dict): Dictionary of words with specific translation rules

    Note:
        - Only processes files in the 'ru/' directory
        - Translates .md files and copies all other files
        - Creates target language directory structure as needed
    """
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
    """
    Translates a Markdown file while preserving its formatting and structure.

    Args:
        file_path (str): Path to the source Markdown file
        new_file_path (str): Path where the translated file should be saved
        target_language (str): Target language code for translation
        translator (Translator): Translator instance to use
        strict_words (dict): Dictionary of words with specific translation rules

    Note:
        - Preserves Markdown formatting including headers, lists, and code blocks
        - Handles frontmatter sections (between '---' markers) specially
        - Uses caching to avoid re-translating previously translated content
        - Creates target directories if they don't exist
    """
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
            content, target_language, strict_words=strict_words, use_cache=True, cache_file="_/md_cache.json", additional_prompt=additional_prompt
        )

        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)

        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)

        logging.info(f"Translated {file_path} -> {new_file_path}")
    except Exception as e:
        logging.exception(f"Exception occurred while translating file {file_path}: {e}")

def copy_file(file_path, new_file_path):
    """
    Copies a non-Markdown file to the target language directory structure.

    Args:
        file_path (str): Path to the source file
        new_file_path (str): Path where the file should be copied

    Note:
        - Creates target directories if they don't exist
        - Performs a binary copy to handle all file types
        - Logs success or failure of the copy operation
    """
    try:
        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
        with open(file_path, 'rb') as src_file:
            with open(new_file_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
        logging.info(f"Copied {file_path} -> {new_file_path}")
    except Exception as e:
        logging.exception(f"Exception occurred while copying file {file_path}: {e}")

if __name__ == "__main__":
    """
    Main execution block for the translation script.

    Usage:
        python script.py <target_language> [commit_hash]

    Args:
        target_language: The language code to translate to
        commit_hash: (Optional) Specific commit to process files from

    Note:
        - Requires OPENAI_API_KEY environment variable to be set
        - If no commit_hash is provided, processes all files in 'ru/' directory
        - Exits with error if required arguments or API key are missing
    """
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