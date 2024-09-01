import os
import logging
from git import Repo
from translator import Translator

# Configuring logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format='%(asctime)s - %(levelname)s - %(message)s')

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

def process_files(changes, target_language, translator):
    for file_path, stats in changes.items():
        logging.info(f"Processing file: {file_path}")
        
        if not file_path.startswith('ru/'):
            continue

        new_file_path = file_path.replace('ru/', f'{target_language}/')

        # Determine the action to take based on stats
        if stats['lines'] == 0:  # This can be used as an indicator of deletion
            if os.path.exists(new_file_path):
                os.remove(new_file_path)
                logging.info(f"Deleted {new_file_path}")
            continue

        if file_path.endswith('.md'):
            translate_markdown(file_path, new_file_path, target_language, translator)
        else:
            copy_file(file_path, new_file_path)

def translate_markdown(file_path, new_file_path, target_language, translator):
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

        translated_content = translator.translate(
            content, target_language, use_cache=True, additional_prompt=additional_prompt
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

    if len(sys.argv) != 3:
        logging.error("Usage: python script.py <commit_hash> <target_language>")
        sys.exit(1)

    commit_hash = sys.argv[1]
    target_language = sys.argv[2]

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.critical("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    translator = Translator(api_key)

    changed_files = get_changed_files(commit_hash)

    if not changed_files:
        logging.warning("No files to process.")
        sys.exit(0)

    process_files(changed_files, target_language, translator)
    