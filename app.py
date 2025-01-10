# Import necessary modules and libraries
from flask import Flask, request, jsonify, session
from pymongo import MongoClient
from flask_cors import CORS
from bson.objectid import ObjectId
import bcrypt
import openai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create the Flask app instance
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing (CORS)
app.secret_key = os.getenv('SECRET_KEY')  # Secret key from environment variable
app.config['SESSION_TYPE'] = 'filesystem'

# MongoDB configuration from environment variables
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')

# OpenAI configuration
openai.api_key = os.getenv('API_KEY')

# Helper functions
def get_db():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(stored_hash, password):
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash)

# Property model class
class Property:
    def __init__(self, title, location, status, property_type, description, price_per_night, img):
        self._id = ObjectId()
        self.title = title
        self.location = location
        self.property_type = property_type
        self.description = description
        self.price_per_night = price_per_night
        self.status = status
        self.img = img

# Booking model class
class Booking:
    def __init__(self, property_img, property_id, property_title, price_per_night, property_location, book_date, end_date):
        self._id = ObjectId()
        self.property_id = property_id
        self.property_title = property_title
        self.price_per_night = price_per_night
        self.property_location = property_location
        self.property_img = property_img
        self.book_date = book_date
        self.end_date = end_date

# Route to handle the root URL
@app.route("/")
def index():
    return "Server running"

# User routes
@app.route('/signup/host', methods=['POST'])
def host_signup():
    db = get_db()
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if db.hosts.find_one({"email": email}):
        return jsonify({"error": "Email already exists"}), 400

    hashed_password = hash_password(password)
    host_id = db.hosts.insert_one({
        "email": email,
        "password": hashed_password,
    }).inserted_id

    return jsonify({"host_id": str(host_id)}), 201

@app.route('/signup/guest', methods=['POST'])
def guest_signup():
    db = get_db()
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if db.guests.find_one({"email": email}):
        return jsonify({"error": "Email already exists"}), 400

    hashed_password = hash_password(password)
    guest_id = db.guests.insert_one({
        "email": email,
        "password": hashed_password,
    }).inserted_id

    return jsonify({"guest_id": str(guest_id)}), 201

@app.route('/login/host', methods=['POST'])
def host_login():
    db = get_db()
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    host = db.hosts.find_one({"email": email})
    if not host or not verify_password(host['password'], password):
        return jsonify({"error": "Invalid credentials"}), 401

    session['user_role'] = 'host'
    return jsonify({"message": "Host login successful", "host_id": str(host["_id"])}), 200

@app.route('/login/guest', methods=['POST'])
def guest_login():
    db = get_db()
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    guest = db.guests.find_one({"email": email})
    if not guest or not verify_password(guest['password'], password):
        return jsonify({"error": "Invalid credentials"}), 401

    session['user_role'] = 'guest'
    return jsonify({"message": "Guest login successful"}), 200

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_role', None)
    return jsonify({"message": "Logout successful"}), 200

# Property routes
@app.route("/api/properties", methods=["GET"])
def get_all_properties():
    db = get_db()
    sort_by = request.args.get('sort_by', 'price_per_night')
    sort_order = int(request.args.get('sort_order', 1))
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 9))
    title_filter = request.args.get('title', '')
    property_type_filter = request.args.get('property_type', '')
    location_filter = request.args.get('location', '')

    filter_query = {}
    if title_filter:
        filter_query['title'] = {'$regex': title_filter, '$options': 'i'}
    if property_type_filter:
        filter_query['property_type'] = property_type_filter
    if location_filter:
        filter_query['location'] = location_filter

    total_properties = db.properties.count_documents(filter_query)
    total_pages = (total_properties - 1) // per_page + 1
    page = max(1, min(page, total_pages))
    skip = (page - 1) * per_page
    skip = max(0, skip)

    properties = db.properties.find(filter_query).skip(skip).limit(per_page)
    if sort_by:
        properties = properties.sort(sort_by, sort_order)

    res = []
    for property in properties:
        res.append({
            "id": str(property["_id"]),
            "title": str(property['title']),
            "location": str(property['location']),
            "property_type": str(property['property_type']),
            "description": str(property['description']),
            "price_per_night": str(property['price_per_night']),
            "status": str(property['status']),
            "img": str(property['img'])
        })

    return jsonify(res)

@app.route("/api/properties/<string:property_id>", methods=["GET"])
def get_property(property_id):
    db = get_db()
    property = db.properties.find_one({"_id": ObjectId(property_id)})
    if property:
        res = {
            "id": str(property["_id"]),
            "title": str(property["title"]),
            "location": str(property["location"]),
            "property_type": str(property["property_type"]),
            "description": str(property["description"]),
            "price_per_night": str(property["price_per_night"]),
            "status": bool(property["status"]),
            "img": str(property["img"])
        }
        return jsonify(res)
    return jsonify({"message": "Property not found"}), 404

@app.route("/api/properties", methods=["POST"])
def create_property():
    db = get_db()
    data = request.get_json()
    property = Property(
        title=data["title"],
        location=data["location"],
        property_type=data["property_type"],
        description=data["description"],
        price_per_night=data["price_per_night"],
        status=data["status"],
        img=data["img"]
    )
    db.properties.insert_one(property.__dict__)
    return jsonify({"message": "Property created successfully"}), 201

@app.route("/api/properties/<string:property_id>", methods=["PUT"])
def update_property(property_id):
    db = get_db()
    data = request.get_json()
    db.properties.update_one({"_id": ObjectId(property_id)}, {"$set": data})
    return jsonify({"message": "Property updated successfully"})

@app.route("/api/properties/<string:property_id>", methods=["DELETE"])
def delete_property(property_id):
    db = get_db()
    result = db.properties.delete_one({"_id": ObjectId(property_id)})
    if result.deleted_count > 0:
        return jsonify({"message": "Property deleted successfully"})
    return jsonify({"message": "Property not found"}), 404

# Booking routes
@app.route("/api/properties/book", methods=["POST"])
def post_property_to_book_collection():
    db = get_db()
    data = request.get_json()

    property_id = data.get('property_id')
    property_title = data.get('property_title')
    price_per_night = data.get('price_per_night')
    property_location = data.get('property_location')
    property_img = data.get('property_img')
    book_date = data.get('book_date')
    end_date = data.get('end_date')

    booking = Booking(
        property_id=property_id,
        property_title=property_title,
        price_per_night=price_per_night,
        property_location=property_location,
        property_img=property_img,
        book_date=book_date,
        end_date=end_date
    )

    booking_id = db.book.insert_one(booking.__dict__).inserted_id

    if property_id:
        db.properties.update_one({"_id": ObjectId(property_id)}, {"$set": {"status": False}})

    return jsonify({"booking_id": str(booking_id)}), 201

@app.route("/api/properties/book", methods=["GET"])
def get_all_book_data():
    db = get_db()
    book_data = db.book.find()
    res = []
    for book_entry in book_data:
        res.append({
            "booking_id": str(book_entry["_id"]),
            "property_id": str(book_entry.get("property_id")),
            "property_title": str(book_entry.get("property_title")),
            "price_per_night": str(book_entry.get("price_per_night")),
            "property_location": str(book_entry.get("property_location")),
            "property_img": str(book_entry.get("property_img")),
            "book_date": str(book_entry.get("book_date")),
            "end_date": str(book_entry.get("end_date"))
        })
    return jsonify(res)

@app.route("/api/properties/book/<string:booking_id>", methods=["GET"])
def get_book_data(booking_id):
    db = get_db()
    book_entry = db.book.find_one({"_id": ObjectId(booking_id)})
    if book_entry:
        res = {
            "booking_id": str(book_entry["_id"]),
            "property_id": str(book_entry.get("property_id")),
            "property_title": str(book_entry.get("property_title")),
            "price_per_night": str(book_entry.get("price_per_night")),
            "property_location": str(book_entry.get("property_location")),
            "property_img": str(book_entry.get("property_img")),
            "book_date": str(book_entry.get("book_date")),
            "end_date": str(book_entry.get("end_date"))
        }
        return jsonify(res)
    return jsonify({"message": "Booking data not found"}), 404

@app.route("/api/properties/book/<string:booking_id>", methods=["DELETE"])
def delete_book_data(booking_id):
    db = get_db()
    book_entry = db.book.find_one({"_id": ObjectId(booking_id)})
    if book_entry:
        property_id = book_entry.get("property_id")
        result = db.book.delete_one({"_id": ObjectId(booking_id)})
        if result.deleted_count > 0:
            if property_id:
                db.properties.update_one({"_id": ObjectId(property_id)}, {"$set": {"status": True}})
            return jsonify({"message": "Booking data deleted successfully"})
    return jsonify({"message": "Booking data not found"}), 404

# Chatbot routes
@app.route('/api/chat', methods=['POST'])
def chat():
    user_input = request.json['user_input']
    response = get_chatbot_response(user_input)
    return jsonify({'response': response})

def get_chatbot_response(user_input):
    if not user_input.strip():
        return "How can I assist you?"

    greetings = ["hi", "hello", "hey"]
    if user_input.lower() in greetings:
        return "Yes, hello! How can I help you?"

    if "hotel" in user_input.lower():
        return get_hotel_response(user_input)

    try:
        chatbot_response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=f"User: {user_input}\nChatGPT:",
            temperature=0.7,
            max_tokens=150
        )
        return chatbot_response['choices'][0]['text'].strip()
    except Exception as e:
        return "I'm sorry, but I couldn't understand your question. Please try again later."

def get_hotel_response(user_input):
    # Your existing hotel response logic here
    # (The function is too long to include here, but remains unchanged)
    pass

if __name__ == '__main__':
    # Get port from environment variable with a default value
    port = int(os.getenv('PORT', 8080))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('FLASK_ENV') == 'development'
    
    app.run(host=host, port=port, debug=debug)