import subprocess
import logging

logger = logging.getLogger(__name__)

class CalculatorService:
    def __init__(self):
        self.name = "calculator"
        logger.info("Calculator service initialized")

    def open_calculator(self):
        try:
            logger.info("Attempting to open calculator...")
            subprocess.Popen('calc.exe')
            logger.info("Calculator opened successfully")
            return True
        except Exception as e:
            logger.error(f"Error opening calculator: {e}")
            return False

    @staticmethod
    def check_calculator_flag(response_data):
        try:
            logger.info(f"Checking calculator flag in response: {response_data}")
            flag = response_data.get('calculator_requested', False)
            logger.info(f"Calculator flag value: {flag}")
            return flag
        except Exception as e:
            logger.error(f"Error checking calculator flag: {e}")
            return False
