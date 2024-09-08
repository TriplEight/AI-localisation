import requests
import logging
import os

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=log_level,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

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