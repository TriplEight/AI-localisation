import os
import requests
import slugify
import yaml
import argparse
import re
import logging
import shutil
import pypandoc
from translator import Translator
import json
from aisystant import Aisystant

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=log_level,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Setting up headers for the API
headers = {
    "Session-Token": os.environ.get("AISYSTANT_SESSION_TOKEN"),
}

# Load strict words from a static file if it exists
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

def save_markdown(directory, filename, frontmatter, text):
    """
    Save the given text as a Markdown file with frontmatter.

    Args:
        directory (str): The directory where the file will be saved.
        filename (str): The name of the Markdown file.
        frontmatter (dict): A dictionary containing frontmatter data.
        text (str): The content to be written to the Markdown file.
    """
    logger.info(f"Saving markdown file: {os.path.join(directory, filename)}")
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding='utf-8') as f:
        f.write("---\n")
        f.write(yaml.dump(frontmatter, allow_unicode=True))
        f.write("---\n\n")
        f.write(text)

def process_images_in_html(html, base_url, directory, prefix):
    """
    Download images from HTML content and save them to a specified directory.

    Args:
        html (str): The HTML content containing image tags.
        base_url (str): The base URL to construct full image URLs.
        directory (str): The directory where images will be saved.
        prefix (str): A prefix to prepend to the image filenames.

    Returns:
        str: The modified HTML content with image paths updated to local filenames.
    """
    logger.debug("Processing images in HTML content.")
    img_tags = re.findall(r'<img src="(/text/[^"]*)" alt="[^"]*">', html)
    os.makedirs(directory, exist_ok=True)

    for img_tag in img_tags:
        full_url = base_url + img_tag
        new_filename = f"{prefix}-{os.path.basename(img_tag)}"
        response = requests.get(full_url, headers=headers)
        if response.status_code == 200:
            with open(os.path.join(directory, new_filename), 'wb') as img_file:
                img_file.write(response.content)
            logger.debug(f"Downloaded and saved image: {new_filename}")
            html = html.replace(img_tag, new_filename)
        else:
            logger.error(f"Failed to download image from {full_url}")
    return html

def process_footnotes_in_html(html_content):
    """
    Extract and replace footnotes in HTML content with custom markers.

    Args:
        html_content (str): The HTML content containing footnotes.

    Returns:
        str: The modified HTML content with footnotes replaced by custom markers.
    """
    # Regex pattern to extract footnotes
    footnote_pattern = re.compile(
        r'<span class="sspopup" onclick="document\.getElementById\(\'(.+?)\'\)\.classList\.toggle\(\'show\'\)\">'
        r'<sup>(\d+)</sup><span class="sspopuptext" id="\1">\[x\] (.+?)</span></span>'
    )

    # Replace footnotes with custom markers
    return re.sub(footnote_pattern, r"{{{begincomment}}}\3{{{endcomment}}}", html_content)

def clean_markdown_text(text):
    """
    Clean unnecessary blocks from Markdown text.

    Args:
        text (str): The Markdown text to be cleaned.

    Returns:
        str: The cleaned Markdown text without unnecessary blocks.
    """
    # Remove unnecessary ::: blocks and their contents
    text = re.sub(r':::\s*\{[^}]*\}', '', text)  # Removes ::: {style="..."}
    text = re.sub(r':::', '', text)  # Removes remaining :::
    return text

def convert_html_to_markdown(html):
    """
    Convert HTML content to Markdown format.

    Args:
        html (str): The HTML content to be converted.

    Returns:
        str: The converted Markdown text.
    """
    logger.debug("Converting HTML to Markdown")

    # Process footnotes before converting HTML to Markdown
    html = process_footnotes_in_html(html)

    # Use pypandoc to convert HTML to Markdown
    markdown_text = pypandoc.convert_text(html, 'md', format='html')

    # Replace the custom markers with actual footnote syntax in Markdown
    markdown_text = markdown_text.replace("{{{begincomment}}}", "^[").replace("{{{endcomment}}}", "]")

    # Optionally, add a new line between footnotes for clarity
    markdown_text = re.sub(r'(\[\^\d+\]: .+?)(\[\^\d+\]: )', r'\1\n\n\2', markdown_text)

    # Clean unnecessary block styles
    markdown_text = clean_markdown_text(markdown_text)

    return markdown_text

def clean_slug(slug):
    """
    Clean a slug by removing leading numbers followed by a hyphen.

    Args:
        slug (str): The slug to be cleaned.

    Returns:
        str: The cleaned slug.
    """
    # Remove leading numbers followed by a hyphen
    slug = re.sub(r'^[0-9]+-*', '', slug)
    return slug

def remove_directory(directory):
    """
    Remove a directory and its contents if it exists.

    Args:
        directory (str): The path to the directory to be removed.
    """
    if os.path.exists(directory):
        logger.info(f"Removing directory: {directory}")
        shutil.rmtree(directory)
    else:
        logger.debug(f"Directory does not exist: {directory}")

def download_course(course_name):
    """
    Download a course by its name, translating sections and saving them as Markdown files.

    Args:
        course_name (str): The name of the course to download.
    """
    # Remove 'ru' directory before starting
    remove_directory('ru')

    aisystant = Aisystant(os.environ.get("AISYSTANT_SESSION_TOKEN"))
    course = aisystant.get_course(course_name)
    if not course:
        logger.error(f"Course with code {course_name} not found.")
        return

    course_version_id = course["activeVersionId"]
    aisystant.start_course(course_version_id)
    passing_id = aisystant.get_passing_id(course_version_id)
    course_version = aisystant.get_course_version(course_version_id)

    # Initialize the translator with API key from environment and load strict words
    api_key = os.environ.get("OPENAI_API_KEY")
    translator = Translator(api_key)
    strict_words = load_strict_words()

    chapter_counter = 0
    section_counter = 0
    parent_directory = ""

    for section in course_version["sections"]:
        if section["type"] == "HEADER" or chapter_counter == 0:
            chapter_counter += 1
            section_counter = 0
            translated_title = translator.translate(section['title'], "English", strict_words, use_cache=True)
            logger.debug(f"Translated title for chapter: {translated_title}")

            if chapter_counter > 1:
                parent_directory = f"{chapter_counter:02d}-{clean_slug(slugify.slugify(translated_title))}"
            else:
                parent_directory = ""

        if section["type"] == "TEXT":
            section_counter += 1

            if parent_directory:
                directory = os.path.join("ru", parent_directory)
            else:
                directory = "ru"

            translated_title = translator.translate(section['title'], "English", strict_words, use_cache=True)
            logger.debug(f"Translated title for section: {translated_title}")
            section_slug = f"{section_counter:02d}-{clean_slug(slugify.slugify(translated_title))}"
            filename = f"{section_slug}.md"
            text = aisystant.load_section(section["id"], passing_id)

            frontmatter = {"title": section['title']}
            text = process_images_in_html(text, "https://aisystant.system-school.ru", directory, section_slug)
            text = convert_html_to_markdown(text)

            save_markdown(directory, filename, frontmatter, text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and save a course.")
    parser.add_argument("course_name", type=str, help="Course code to download")

    args = parser.parse_args()
    download_course(args.course_name)