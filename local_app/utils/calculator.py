import logging
import subprocess

logger = logging.getLogger(__name__)

def open_calculator() -> bool:
    """Open Windows calculator
    
    Returns:
        bool: True if calculator was opened successfully, False otherwise
    """
    try:
        logger.warning("Opening calculator...")
        subprocess.Popen('calc.exe')
        logger.info("Calculator opened successfully")
        return True
    except Exception as e:
        logger.error(f"Error opening calculator: {e}")
        return False
