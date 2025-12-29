from flask import Flask, jsonify, request, render_template, make_response
from datetime import datetime, timedelta
from dateutil import parser
import requests
from bs4 import BeautifulSoup
import os
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# Cache duration in seconds (2 hours for API, configurable via environment)
CACHE_DURATION = int(os.getenv('CACHE_DURATION', 7200))
# Static files cache duration (1 week)
STATIC_CACHE_DURATION = int(os.getenv('STATIC_CACHE_DURATION', 604800))
# HTML pages cache duration (30 minutes)
HTML_CACHE_DURATION = int(os.getenv('HTML_CACHE_DURATION', 1800))

# Configure session for connection pooling and retry strategy
def create_session():
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,  # Maximum number of retries
        backoff_factor=0.5,  # Backoff factor for retries
        status_forcelist=[429, 500, 502, 503, 504],  # Status codes to retry on
    )
    
    # Mount the adapter with the retry strategy for both http and https
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# Global session object for connection pooling
http_session = create_session()

# Maximum number of workers for parallel requests
MAX_WORKERS = 5

class EdtElement:
    def __init__(self, name=None, room=None, teacher=None, date=None, start_time=None, end_time=None):
        self.name = name.split('\r\n')[0] if name else None
        self.room = room
        self.teacher = teacher
        self.date = date
        self.start_time = start_time
        self.end_time = end_time

    def to_dict(self):
        return {
            "name": self.name,
            "room": self.room,
            "teacher": self.teacher,
            "date": self.date.strftime("%Y-%m-%d") if self.date else "",
            "start_time": self.start_time,
            "end_time": self.end_time
        }

def get_day(search_date, search_user):
    query_date = search_date.strftime("%m/%d/%Y")
    url = f"https://edtmobiliteng.wigorservices.net/WebPsDyn.aspx?Action=posETUD&serverid=C&Tel={search_user}&date={query_date}%208:00"
    
    try:
        # Use the global session for connection pooling
        response = http_session.get(url, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch schedule: {response.status_code}")
        
        # Use lxml parser for better performance
        soup = BeautifulSoup(response.text, 'lxml')
        edt_elements = []
        
        # Find all elements with one query to improve performance
        lines = soup.find_all('div', class_='Ligne')
        
        for line in lines:
            name = line.find('div', class_='Matiere')
            room = line.find('div', class_='Salle')
            teacher = line.find('div', class_='Prof')
            start_time = line.find('div', class_='Debut')
            end_time = line.find('div', class_='Fin')
            
            room_text = room.text.strip() if room else None
            if room_text:
                if room_text.startswith("SALLE_"):
                    room_text = "DISTANCIEL"
                elif not room_text.startswith("T "):
                    room_text = "Inconnue"

            edt_element = EdtElement(
                name=name.text.strip() if name else None,
                room=room_text,
                teacher=teacher.text.strip() if teacher else None,
                date=search_date,
                start_time=start_time.text.strip() if start_time else None,
                end_time=end_time.text.strip() if end_time else None
            )
            edt_elements.append(edt_element)
        
        if not edt_elements:
            edt_elements.append(EdtElement(date=search_date))
            
    except Exception as e:
        edt_elements = [EdtElement(
            name="Impossible de récupérer l'emploi du temps",
            room="ERROR001",
            date=search_date,
            teacher=str(e),
            start_time="00:00",
            end_time="23:59"
        )]
    
    return edt_elements

def get_edt_elements(begin_date, end_date, user):
    dates = []
    current_date = begin_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday to Friday
            dates.append(current_date)
        current_date += timedelta(days=1)
    
    results = [None] * len(dates)  # Pre-allocate results list
    
    # Use ThreadPoolExecutor for parallel requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(dates))) as executor:
        # Submit all tasks
        future_to_date = {executor.submit(get_day, date, user): i for i, date in enumerate(dates)}
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_date):
            date_index = future_to_date[future]
            try:
                results[date_index] = future.result()
            except Exception as e:
                # Handle any exceptions that might have occurred
                results[date_index] = [EdtElement(
                    name="Erreur lors du traitement de l'emploi du temps",
                    room="ERROR002",
                    date=dates[date_index],
                    teacher=str(e),
                    start_time="00:00",
                    end_time="23:59"
                )]
    
    return results

def add_cache_headers(response, cache_type='default'):
    """Add comprehensive cache control headers for browser and CDN caching"""
    
    if cache_type == 'static':
        # Static assets (CSS, JS, images) - cache for configured duration
        response.headers['Cache-Control'] = f'public, max-age={STATIC_CACHE_DURATION}, s-maxage={STATIC_CACHE_DURATION}, immutable'
        response.headers['Expires'] = (datetime.utcnow() + timedelta(seconds=STATIC_CACHE_DURATION)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    elif cache_type == 'api':
        # API responses - cache for configured duration with stale-while-revalidate
        response.headers['Cache-Control'] = f'public, max-age={CACHE_DURATION}, s-maxage={CACHE_DURATION}, stale-while-revalidate=86400'
        response.headers['Expires'] = (datetime.utcnow() + timedelta(seconds=CACHE_DURATION)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    elif cache_type == 'no-cache':
        # Force fresh data (for refresh requests)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif cache_type == 'health':
        # Health check - short cache
        response.headers['Cache-Control'] = 'public, max-age=60, s-maxage=60'
        response.headers['Expires'] = (datetime.utcnow() + timedelta(seconds=60)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    else:  # default
        # Default caching for HTML pages
        response.headers['Cache-Control'] = f'public, max-age={HTML_CACHE_DURATION}, s-maxage={HTML_CACHE_DURATION}'
        response.headers['Expires'] = (datetime.utcnow() + timedelta(seconds=HTML_CACHE_DURATION)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # Common headers for all responses
    response.headers['Vary'] = 'Accept-Encoding, User-Agent'
    response.headers['X-Cache-Status'] = 'MISS'  # Cloudflare will override this
    
    # ETag for better cache validation (simple hash of content)
    if hasattr(response, 'data') and response.data:
        import hashlib
        etag = hashlib.md5(response.data).hexdigest()
        response.headers['ETag'] = f'"{etag}"'
    
    return response

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files with optimal caching headers"""
    try:
        response = make_response(app.send_static_file(filename))
        return add_cache_headers(response, 'static')
    except Exception:
        return "File not found", 404

@app.before_request
def handle_conditional_requests():
    """Handle conditional requests with ETag and If-None-Match"""
    if request.method == 'GET':
        # Check If-None-Match header for ETag validation
        if_none_match = request.headers.get('If-None-Match')
        if if_none_match:
            # For simplicity, we'll let the route handler set the ETag
            # and the browser will handle 304 responses automatically
            pass

@app.after_request
def after_request(response):
    """Add security and performance headers to all responses"""
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Performance headers
    response.headers['Server'] = 'EPSI-EDT-API'
    
    # CORS headers for API endpoints
    if request.endpoint and ('schedule' in request.endpoint or 'week' in request.endpoint):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '86400'
    
    return response

@app.route('/', methods=['GET'])
def get_schedule():
    response = make_response(render_template('index.html'))
    return add_cache_headers(response, 'default')

@app.route('/<date>', methods=['GET'])
def get_schedule_by_date(date):
    user = request.args.get('user')
    no_cache = request.args.get('_')  # Timestamp parameter for cache busting
    
    if not user:
        return jsonify({"error": "User parameter is required"}), 400
    
    try:
        search_date = parser.parse(date, dayfirst=True).date()
        results = get_day(search_date, user)
        
        # Convert results to JSON format
        schedule_data = [element.to_dict() for element in results]
        
        # Create response with appropriate cache headers
        response = make_response(jsonify(schedule_data))
        cache_type = 'no-cache' if no_cache else 'api'
        return add_cache_headers(response, cache_type)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/week/<date>', methods=['GET'])
def get_schedule_by_week(date):
    user = request.args.get('user')
    no_cache = request.args.get('_')  # Timestamp parameter for cache busting
    
    if not user:
        return jsonify({"error": "User parameter is required"}), 400
    
    try:
        # Parse the given date
        search_date = parser.parse(date, dayfirst=True).date()
        
        # Calculate the Monday and Sunday of the week containing the given date
        weekday = search_date.weekday()  # 0 is Monday, 6 is Sunday
        begin_date = search_date - timedelta(days=weekday)  # Monday
        end_date = begin_date + timedelta(days=6)  # Sunday
        
        results = get_edt_elements(begin_date, end_date, user)
        
        # Convert results to JSON format
        schedule_data = []
        for day in results:
            day_data = []
            for element in day:
                day_data.append(element.to_dict())
            schedule_data.append(day_data)
          # Create response with appropriate cache headers
        response = make_response(jsonify(schedule_data))
        cache_type = 'no-cache' if no_cache else 'api'
        return add_cache_headers(response, cache_type)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint with minimal caching"""
    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "cache_duration": CACHE_DURATION,
        "version": "1.0"
    }
    response = make_response(jsonify(health_data))
    return add_cache_headers(response, 'health')

@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Handle CORS preflight requests"""
    response = make_response('', 200)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, If-None-Match'
    response.headers['Access-Control-Max-Age'] = '86400'
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

if __name__ == '__main__':
    app.run(debug=True)