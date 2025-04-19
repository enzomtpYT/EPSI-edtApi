from flask import Flask, jsonify, request, render_template, make_response
from datetime import datetime, timedelta
from dateutil import parser
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

# Cache duration in seconds (2 hours)
CACHE_DURATION = int(os.getenv('CACHE_DURATION', 7200))

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
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch schedule: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        edt_elements = []
        
        for line in soup.find_all('div', class_='Ligne'):
            name = line.find('div', class_='Matiere')
            room = line.find('div', class_='Salle')
            teacher = line.find('div', class_='Prof')
            start_time = line.find('div', class_='Debut')
            end_time = line.find('div', class_='Fin')
            
            edt_element = EdtElement(
                name=name.text.strip() if name else None,
                room="DISTANCIEL" if room and room.text.strip().startswith("SALLE_") else (room.text.strip() if room else None),
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
    
    results = []
    for date in dates:
        results.append(get_day(date, user))
    return results

def add_cache_headers(response):
    """Add cache control headers for Cloudflare caching"""
    response.headers['Cache-Control'] = f'public, max-age={CACHE_DURATION}'
    return response

@app.route('/', methods=['GET'])
def get_schedule():
    return render_template('index.html')

@app.route('/<date>', methods=['GET'])
def get_schedule_by_date(date):
    user = request.args.get('user')
    
    if not user:
        return jsonify({"error": "User parameter is required"}), 400
    
    try:
        search_date = parser.parse(date, dayfirst=True).date()
        results = get_day(search_date, user)
        
        # Convert results to JSON format
        schedule_data = [element.to_dict() for element in results]
        
        # Create response with cache headers
        response = make_response(jsonify(schedule_data))
        return add_cache_headers(response)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/week/<date>', methods=['GET'])
def get_schedule_by_week(date):
    user = request.args.get('user')
    
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
        
        # Create response with cache headers
        response = make_response(jsonify(schedule_data))
        return add_cache_headers(response)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)