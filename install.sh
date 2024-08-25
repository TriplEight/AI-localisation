#!/bin/bash

# Update package lists to get the latest version of repositories
sudo apt-get update

# Install Pandoc for document conversion
sudo apt-get install -y pandoc

# Install Python dependencies from requirements.txt
pip install -r course-publish-tools/requirements.txt

echo "Installation completed."
