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
    """
    A client for interacting with the Aisystant API.
    Provides methods for course management and content retrieval.
    """

    def __init__(self, api_token):
        """
        Initialize the Aisystant API client.

        Args:
            api_token (str): Authentication token for API access
        """
        self.api_token = api_token
        self.base_url = 'https://api.aisystant.com/api'
        self.headers = {'Session-Token': api_token}

    def get(self, path, **kwargs):
        """
        Generic GET request handler for the Aisystant API.

        Args:
            path (str): API endpoint path to request
            **kwargs: Additional arguments to pass to requests.get()

        Returns:
            dict: JSON response from the API

        Raises:
            requests.exceptions.HTTPError: If the API request fails
        """
        logger.debug(f"Sending GET request to {self.base_url}/{path} with headers {self.headers}")
        response = requests.get(f'{self.base_url}/{path}', headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_course(self, product_code):
        """
        Retrieve course information by its product code.

        Args:
            product_code (str): Unique identifier for the course

        Returns:
            dict: Course information if found
            None: If no course matches the product code
        """
        logger.info(f"Fetching course with product code: {product_code}")
        courses = self.get('courses/courses')
        for course in courses:
            if course['productCode'] == product_code:
                logger.debug(f"Found course: {course}")
                return course
        logger.warning(f"Course with product code {product_code} not found.")
        return None

    def get_course_version(self, course_version_id):
        """
        Retrieve specific version information for a course.

        Args:
            course_version_id (str): Unique identifier for the course version

        Returns:
            dict: Course version information

        Raises:
            requests.exceptions.HTTPError: If the API request fails
        """
        logger.info(f"Fetching course version with ID: {course_version_id}")
        return self.get(f'courses/course-versions/{course_version_id}')

    def start_course(self, course_version_id):
        """
        Initialize a course version for the current user.

        Args:
            course_version_id (str): Unique identifier for the course version

        Raises:
            requests.exceptions.HTTPError: If the API request fails
        """
        logger.info(f"Starting course version with ID: {course_version_id}")
        response = requests.post(f'{self.base_url}/courses/start/{course_version_id}', headers=self.headers)
        response.raise_for_status()

    def get_passing_id(self, course_version_id):
        """
        Retrieve the passing ID for a specific course version.
        The passing ID represents a user's progress/attempt in a course.

        Args:
            course_version_id (str): Unique identifier for the course version

        Returns:
            str: Passing ID if found
            None: If no passing ID exists for the course version
        """
        logger.info(f"Fetching passing ID for course version ID: {course_version_id}")
        passings = self.get('courses/courses-passing')
        for passing in passings:
            if passing["courseVersionId"] == course_version_id:
                logger.debug(f"Found passing ID: {passing['id']}")
                return passing["id"]
        logger.warning(f"No passing ID found for course version ID: {course_version_id}")
        return None

    def load_section(self, section_id, passing_id):
        """
        Load content for a specific section of a course.

        Args:
            section_id (str): Unique identifier for the course section
            passing_id (str): Passing ID representing the user's course attempt

        Returns:
            str: Section content in UTF-8 encoding

        Raises:
            requests.exceptions.HTTPError: If the API request fails
        """
        logger.info(f"Loading section {section_id} for passing ID: {passing_id}")
        url = f"{self.base_url}/courses/text/{section_id}?course-passing={passing_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.content.decode('utf-8', errors='replace')
