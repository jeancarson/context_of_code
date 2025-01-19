from flask import Flask
from lib_config.config import Config
import sys
import logging
# Load configuration
config = Config('config.json')

# Initialize Flask app with configuration
app = Flask(__name__)
app.config['DEBUG'] = config.debug
app.config['SECRET_KEY'] = config.flask.secret_key

logger = logging.getLogger(__name__)
config.setup_logging()

# Access configuration values naturally with typeahead and strongly typed.
logger.info("Configured server is: %s", config.database.host)  # "localhost"

logger.debug("This is a sample debug message")
logger.info("This is a sample info message")
logger.warning("This is a sample warning message")
logger.error("This is a sample error message")
logger.critical("This is a sample critical message")

@app.route("/")
def hello():
    logger.info("Hello World!")
    return "Hello World!"

if __name__ == "__main__":
    app.run(
        host=config.flask.host,
        port=config.flask.port
    ) 
    sys.exit(0);