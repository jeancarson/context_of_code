from flask import Flask, jsonify
import psutil
import logging
from datetime import datetime
from block_timer import BlockTimer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/metrics')
def get_metrics():
    with BlockTimer("Get System Metrics", logger):
        try:
            battery = psutil.sensors_battery()
            battery_percent = battery.percent if battery else 0.0
            memory = psutil.virtual_memory()
            
            metrics = {
                'battery_percent': battery_percent,
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / (1024 * 1024),
                'memory_total_mb': memory.total / (1024 * 1024),
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(metrics)
            
        except Exception as e:
            logger.error(f"Failed to get system metrics: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting local metrics publisher on port 5001")
    # Make sure to bind to 0.0.0.0 so it's accessible from other machines
    app.run(host='0.0.0.0', port=5001)
