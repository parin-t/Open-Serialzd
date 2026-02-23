# Open-Serialzd
Serializd Review Automator
A Python automation tool for batch-submitting TV show reviews to Serializd.com from Excel spreadsheets.
Overview
This project automates the process of logging multiple TV show reviews on Serializd by reading structured data from an Excel file and using browser automation to submit each review. Originally built to streamline logging an entire season's worth of reviews at once.
Features

Batch Processing: Submit multiple reviews from a single Excel file
Flexible Input: Supports episode-level and season-level reviews
Smart UI Interaction: Handles date selection, star ratings, and text input automatically
Error Handling: Includes retry logic and graceful error recovery
Configurable: Easy to adapt for different shows and review formats

Tech Stack

Python 3.x
Playwright: Browser automation for interacting with Serializd's UI
Pandas: Reading and processing Excel data
OpenPyXL: Excel file handling

Excel Format
The tool expects an Excel file (reviews.xlsx) with the following columns:
ColumnDescriptionSeasonSeason number (integer)EpisodeEpisode number (leave blank for season reviews)DateReview date (MM/DD/YYYY)RatingStar rating (0-10)Favorite?Mark as favorite (TRUE/FALSE)ReviewReview text
Setup

Install dependencies:

bashpip install playwright pandas openpyxl
playwright install chromium

Set environment variables for Serializd credentials:

bashexport SER_EMAIL="your_email@example.com"
export SER_PASS="your_password"

Update SHOW_NAME variable in the script to match your target show
Prepare your reviews.xlsx file with review data

Usage
bashpython serialxd_automator.py
The script will:

Launch a browser and log into Serializd
Process each row in the Excel file
Submit reviews automatically with the specified data

Notes

The browser runs in non-headless mode so you can monitor progress
Includes built-in delays to mimic human interaction
Credentials are read from environment variables for security

Future Improvements

Command-line arguments for show name and file path
Support for multiple shows in one run
CSV format support
Headless mode option


License
Personal project - use and modify as needed
