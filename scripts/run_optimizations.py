#!/usr/bin/env python
"""
Script to run optimization commands on a schedule.
This can be set up as a cron job or scheduled task.

Example cron entry (runs daily at 3 AM):
0 3 * * * /path/to/venv/bin/python /path/to/Mahna/scripts/run_optimizations.py
"""

import os
import sys
import subprocess
import datetime
import logging

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, 'optimizations.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add the project directory to the path so we can import Django settings
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_dir)

def run_command(command):
    """Run a management command and log the output"""
    try:
        logging.info(f"Running command: {command}")
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        logging.info(f"Command output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e}")
        logging.error(f"Error output: {e.stderr}")
        return False

def main():
    """Run optimization commands"""
    logging.info("Starting optimization tasks")
    
    # Get the Python executable path
    python_executable = sys.executable
    manage_py = os.path.join(project_dir, 'manage.py')
    
    # Clean up expired sessions (older than 1 day)
    run_command(f'"{python_executable}" "{manage_py}" cleanup_sessions --days=1')
    
    # Clear expired cache entries
    run_command(f'"{python_executable}" "{manage_py}" clear_expired_cache')
    
    logging.info("Optimization tasks completed")

if __name__ == "__main__":
    start_time = datetime.datetime.now()
    logging.info(f"Script started at {start_time}")
    
    main()
    
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    logging.info(f"Script completed at {end_time} (duration: {duration})")