from waitress import serve
from app import app
import logging
import time
from flask import request
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('waitress')
logger.setLevel(logging.INFO)

# Request logging middleware
@app.before_request
def start_timer():
    request.start_time = time.time()

@app.after_request
def log_request(response):
    # Calculate response time
    response_time = (time.time() - request.start_time) * 1000  # Convert to milliseconds
    
    # Get request details
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    method = request.method
    path = request.path
    status_code = response.status_code
    user_agent = request.headers.get('User-Agent', 'No User-Agent')
    remote_addr = request.remote_addr
    
    # Log the request details
    logger.info(
        f"Request: {method} {path} | "
        f"Status: {status_code} | "
        f"Response Time: {response_time:.2f}ms | "
        f"IP: {remote_addr} | "
        f"User Agent: {user_agent}"
    )
    
    return response

if __name__ == '__main__':
    print("Starting Waitress server with verbose logging...")
    serve(app, host='0.0.0.0', port=5000, threads=4, _quiet=False) 