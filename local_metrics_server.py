import os
from flask import Flask, jsonify
from system_monitor import SystemMonitor
import logging

app = Flask(__name__)
system_monitor = SystemMonitor()

@app.route("/metrics")
def get_metrics():
    metrics = system_monitor.get_metrics()
    return jsonify(metrics.dict())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)  # Different port than main app
