from flask import *
import twilio.twiml
from twilio.rest import TwilioRestClient
import os 
from pymongo import *

debug = False
i = 0

app = Flask(__name__)

# Twilio account info, to be gotten from Heroku environment variables
account_sid = os.environ['ACCOUNT_SID'] 
auth_token = os.environ['AUTH_TOKEN']
twilionumber = os.environ['TWILIO']
mynumber = os.environ['ME']

# MongoHQ account info, also from Heroku environment variables
mongoclientURL = os.environ['MONGOHQ_URL']
databasename = mongoclientURL.split("/")[-1] #gets the last bit of the URL, which is the database name

client = MongoClient(mongoclientURL)
database = client[databasename]	#loads the assigned database
collection = database["phonenumber"] #loads or makes the collection, whichever should happen



@app.route('/', methods=['GET'])
def index():
	return render_template("template.html", information = collection)

@app.route('/twilio', methods=['POST'])
def handle_form():
	sendtonumber = request.form.get('From', None)
	content = request.form.get('Body', "empty text?")

	
	collection.insert({"position":i, "content":content})
	 # i = i+1

	try:
		client = TwilioRestClient(account_sid, auth_token)
		message = client.sms.messages.create(body="sent from python!", to=sendtonumber, from_=twilionumber)
 	except twilio.TwilioRestException as e:
 		print e
 		return e
 	return sendtonumber+"\n"+content
	
	# render_template("template.html", information = collection)

if __name__ == "__main__":
	app.run(debug=debug)



	# base_url = url_for("index", _external=True)
	# if request.form.get('content', None):