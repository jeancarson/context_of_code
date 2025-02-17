import os
from flask import Flask, jsonify, send_from_directory, request, render_template
from lib.config import Config
import logging
from lib.models.country_commits_model import CountryCommits
from lib.database import init_db, get_session
from lib.constants import StatusCode
import datetime
from sqlalchemy import select, func, and_
import sys

# Compute root directory once and use it throughout the file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize logging first
logger = logging.getLogger(__name__)
config = Config(os.path.join(ROOT_DIR, 'config.json'))
config.setup_logging()

# Initialize Flask app with configuration
app = Flask(__name__)
app.config['DEBUG'] = config.debug
app.config['SECRET_KEY'] = config.server.secret_key

@app.route("/")
def index():
    """Render the main dashboard"""
    return render_template('index.html')

@app.route("/github")
def github_dashboard():
    """Render the GitHub stats dashboard"""
    try:
        with get_session() as db:
            # Get latest stats for each country
            subq = (
                select(CountryCommits.country_code, 
                      func.max(CountryCommits.timestamp).label('max_time'))
                .group_by(CountryCommits.country_code)
                .subquery()
            )
            
            stats = (
                db.query(CountryCommits)
                .join(
                    subq,
                    and_(
                        CountryCommits.country_code == subq.c.country_code,
                        CountryCommits.timestamp == subq.c.max_time
                    )
                )
                .all()
            )
            
            return render_template(
                'github_stats.html',
                countries=[{
                    'country_code': stat.country_code,
                    'country_name': stat.country_name,
                    'population': stat.population,
                    'commit_count': stat.commit_count,
                    'commits_per_capita': stat.commits_per_capita,
                    'timestamp': stat.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
                } for stat in stats],
                last_updated=stats[0].timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if stats else 'Never'
            )
            
    except Exception as e:
        logger.error(f"Error retrieving GitHub stats: {e}")
        return render_template(
            'github_stats.html',
            countries=[],
            last_updated='Error retrieving data',
            error=str(e)
        )

@app.route("/github_stats", methods=["POST"])
def github_stats():
    """Store GitHub stats data received from local app"""
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), StatusCode.BAD_REQUEST
    
    try:
        data = request.get_json()
        stats = data.get('stats')
        
        if not stats:
            return jsonify({"error": "No stats data provided"}), StatusCode.BAD_REQUEST
        
        with get_session() as db:
            # Store each country's stats
            for stat in stats:
                country_stat = CountryCommits(
                    country_code=stat['country_code'],
                    country_name=stat['country_name'],
                    population=stat['population'],
                    commit_count=stat['commit_count'],
                    commits_per_capita=stat['commits_per_capita'],
                    timestamp=datetime.datetime.fromisoformat(stat['timestamp'])
                )
                db.add(country_stat)
            db.commit()
        
        return jsonify({"message": "Stats stored successfully"}), StatusCode.OK
        
    except Exception as e:
        logger.error(f"Error storing GitHub stats: {e}")
        return jsonify({"error": str(e)}), StatusCode.INTERNAL_SERVER_ERROR

@app.route("/github_stats", methods=["GET"])
def get_github_stats():
    """Get stored GitHub stats"""
    try:
        with get_session() as db:
            # Get latest stats for each country
            subq = (
                select(CountryCommits.country_code, 
                      func.max(CountryCommits.timestamp).label('max_time'))
                .group_by(CountryCommits.country_code)
                .subquery()
            )
            
            stats = (
                db.query(CountryCommits)
                .join(
                    subq,
                    and_(
                        CountryCommits.country_code == subq.c.country_code,
                        CountryCommits.timestamp == subq.c.max_time
                    )
                )
                .all()
            )
            
            return jsonify([{
                'country_code': stat.country_code,
                'country_name': stat.country_name,
                'population': stat.population,
                'commit_count': stat.commit_count,
                'commits_per_capita': stat.commits_per_capita,
                'timestamp': stat.timestamp.isoformat()
            } for stat in stats]), StatusCode.OK
            
    except Exception as e:
        logger.error(f"Error retrieving GitHub stats: {e}")
        return jsonify({"error": str(e)}), StatusCode.INTERNAL_SERVER_ERROR

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

if __name__ == "__main__":
    try:
        init_db()
        app.run(
            host=config.server.host,
            port=config.server.port,
            debug=config.debug
        )
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)
