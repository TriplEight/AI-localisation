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
def load_strict_words(file_path="strict_words.json"):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

class Aisystant:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = 'https://api.aisystant.com/api'
        self.headers = {'Session-Token': api_token}

    def get(self, path, **kwargs):
        logger.debug(f"Sending GET request to {self.base_url}/{path} with headers {self.headers}")
        response = requests.get(f'{self.base_url}/{path}', headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_course(self, product_code):
        logger.info(f"Fetching course with product code: {product_code}")
        courses = self.get('courses/courses')
        for course in courses:
            if course['productCode'] == product_code:
                logger.debug(f"Found course: {course}")
                return course
        logger.warning(f"Course with product code {product_code} not found.")
        return None

    def get_course_version(self, course_version_id):
        logger.info(f"Fetching course version with ID: {course_version_id}")
        return self.get(f'courses/course-versions/{course_version_id}')

    def start_course(self, course_version_id):
        logger.info(f"Starting course version with ID: {course_version_id}")
        response = requests.post(f'{self.base_url}/courses/start/{course_version_id}', headers=self.headers)
        response.raise_for_status()

    def get_passing_id(self, course_version_id):
        logger.info(f"Fetching passing ID for course version ID: {course_version_id}")
        passings = self.get('courses/courses-passing')
        for passing in passings:
            if passing["courseVersionId"] == course_version_id:
                logger.debug(f"Found passing ID: {passing['id']}")
                return passing["id"]
        logger.warning(f"No passing ID found for course version ID: {course_version_id}")
        return None

    def load_section(self, section_id, passing_id):
        logger.info(f"Loading section {section_id} for passing ID: {passing_id}")
        url = f"{self.base_url}/courses/text/{section_id}?course-passing={passing_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.content.decode('utf-8', errors='replace')

def save_markdown(directory, filename, frontmatter, text):
    logger.info(f"Saving markdown file: {os.path.join(directory, filename)}")
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding='utf-8') as f:
        f.write("---\n")
        f.write(yaml.dump(frontmatter, allow_unicode=True))
        f.write("---\n\n")
        f.write(text)

def process_images_in_html(html, base_url, directory, prefix):
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
    # Шаблон для поиска сносок
    footnote_pattern = re.compile(
        r'<span class="sspopup" onclick="document\.getElementById\(\'(.+?)\'\)\.classList\.toggle\(\'show\'\)\">'
        r'<sup>(\d+)</sup><span class="sspopuptext" id="\1">\[x\] (.+?)</span></span>'
    )

    # Заменяем HTML сноски на маркеры
    return re.sub(footnote_pattern, r"${begin_comment}\3${end_comment}", html_content)

def convert_html_to_markdown(html):
    logger.debug("Converting HTML to Markdown")
    
    # Process footnotes before converting HTML to Markdown
    html = process_footnotes_in_html(html)
    
    # Use pypandoc to convert HTML to Markdown
    markdown_text = pypandoc.convert_text(html, 'md', format='html')

    # Replace the custom markers with actual footnote syntax in Markdown
    markdown_text = markdown_text.replace("${begin_comment}", "[^").replace("${end_comment}", "]")

    # Optionally, add a new line between footnotes for clarity
    markdown_text = re.sub(r'(\[\^\d+\]: .+?)(\[\^\d+\]: )', r'\1\n\n\2', markdown_text)

    return markdown_text

def clean_slug(slug):
    # Remove leading numbers followed by a hyphen
    slug = re.sub(r'^[0-9]+-*', '', slug)
    return slug

def remove_directory(directory):
    if (os.path.exists(directory)):
        logger.info(f"Removing directory: {directory}")
        shutil.rmtree(directory)
    else:
        logger.debug(f"Directory does not exist: {directory}")

def download_course(course_name):
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

    chapter_counter = 0  # Counter for chapters
    section_counter = 0  # Counter for sections within a chapter
    parent_directory = ""  # Start with an empty parent directory

    for section in course_version["sections"]:
        if section["type"] == "HEADER" or chapter_counter == 0:
            chapter_counter += 1
            section_counter = 0  # Reset section counter for new chapter
            translated_title = translator.translate(section['title'], "English", strict_words, use_cache=True)
            logger.debug(f"Translated title for chapter: {translated_title}")
            parent_directory = f"{chapter_counter:02d}-{clean_slug(slugify.slugify(translated_title))}"

        if section["type"] == "TEXT":
            section_counter += 1
            directory = os.path.join("ru", parent_directory)
            translated_title = translator.translate(section['title'], "English", strict_words, use_cache=True)
            logger.debug(f"Translated title for section: {translated_title}")
            section_slug = f"{section_counter:02d}-{clean_slug(slugify.slugify(translated_title))}"
            filename = f"{section_slug}.md"
            text = aisystant.load_section(section["id"], passing_id)
            # Use the original title in the frontmatter
            frontmatter = {"title": section['title']}
            text = process_images_in_html(text, "https://aisystant.system-school.ru", directory, section_slug)
            text = convert_html_to_markdown(text)  # Convert HTML to Markdown
            save_markdown(directory, filename, frontmatter, text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and save a course.")
    parser.add_argument("course_name", type=str, help="Course code to download")

    args = parser.parse_args()
    download_course(args.course_name)