from flask import Flask, jsonify, request
from datetime import datetime, timedelta
from dateutil import parser
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

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

@app.route('/', methods=['GET'])
def get_schedule():
    user = request.args.get('user')
    begin = request.args.get('begin')
    end = request.args.get('end')
    
    if not user:
        return jsonify({"error": "User parameter is required"}), 400
    
    try:
        begin_date = parser.parse(begin, dayfirst=True).date() if begin else datetime.now().date()
        end_date = parser.parse(end, dayfirst=True).date() if end else begin_date
        
        if begin_date > end_date:
            return jsonify({"error": "Start date cannot be after end date"}), 400
            
        results = get_edt_elements(begin_date, end_date, user)
        
        # Convert results to JSON format
        schedule_data = []
        for day in results:
            day_data = []
            for element in day:
                day_data.append(element.to_dict())
            schedule_data.append(day_data)
            
        return jsonify(schedule_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        return jsonify(schedule_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 