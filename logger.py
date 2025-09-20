from loguru import logger

import sys
 
logger.add("logs/app.log", rotation="500 MB", backtrace=True, diagnose=True)
 