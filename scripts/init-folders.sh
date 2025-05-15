#!/bin/bash

mkdir -p ../discover_site_structure
touch ../discover_site_structure/discover.py
touch ../discover_site_structure/utils.py

mkdir -p ../smart_crawler
touch ../smart_crawler/smart_crawler.py
touch ../smart_crawler/schema.py
touch ../smart_crawler/utils.py

mkdir -p ../prompt_agent
touch ../prompt_agent/lovable_prompter.py
touch ../prompt_agent/utils.py

mkdir -p ../prompt_templates
touch ../prompt_templates/homepage.txt
touch ../prompt_templates/services.txt

mkdir -p ../final_prompts
touch ../final_prompts/lovable_full_prompt.txt

mkdir -p ../outputs
touch ../outputs/discovered_pages.json
touch ../outputs/homepage.json
touch ../outputs/services.json

echo "Folder structure created successfully."

