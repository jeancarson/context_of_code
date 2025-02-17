from lib.database import init_db
import logging

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("Database initialization completed successfully!")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise
