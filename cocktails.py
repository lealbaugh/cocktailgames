from flask import *
import twilio.twiml
from twilio.rest import TwilioRestClient
import os 
from pymongo import *

debug = True
app = Flask(__name__)

# Twilio account info, to be gotten from Heroku environment variables
account_sid = os.environ['ACCOUNT_SID'] 
auth_token = os.environ['AUTH_TOKEN']
twilionumber = os.environ['TWILIO']
mynumber = os.environ['ME']
# Init twilio
twilioclient = TwilioRestClient(account_sid, auth_token)

# MongoHQ account info, also from Heroku environment variables
mongoclientURL = os.environ['MONGOHQ_URL']
databasename = mongoclientURL.split("/")[-1] #gets the last bit of the URL, which is the database name
# Init Mongo
mongoclient = MongoClient(mongoclientURL)
database = mongoclient[databasename]	#loads the assigned database
# collection = database["phonenumber"] #loads or makes the collection, whichever should happen
players = database["players"]
transcript = database["transcript"]


#----------Function Defs-------------------

def sendToRecipient(content, recipient, sender="HQ"):
	recipientnumber = players.find({"agentname":recipient}, {"phonenumber":1, "_id":0})[0]["phonenumber"] 
	#theory: "find" returns an array of objects; the first one ought to be the one we want
	if sender == "HQ":
		sendernumber = twilionumber
	else:
		sendernumber = players.find({"agentname":sender}, {"phonenumber":1, "_id":0})[0]["phonenumber"]

	time = 0 #function here to return time
	transcript.insert({"time":time, "recipient":recipient, "sender":sender, "content":content})
	
	try:
		message = twilioclient.sms.messages.create(body=content, to=recipientnumber, from_=sendernumber)
		transcript.insert({"time":time, "sender":sender, "recipient":recipient, "content":content, "error":"no"})
 	except twilio.TwilioRestException as e:
 		transcript.insert({"time":time, "sender":sender, "recipient":recipient, "content":content, "error":e})


def newPlayer(phonenumber, content):
	# generate agent name
	# add name, agent, init points, etc to players collection
	if phonenumber == os.environ['DAVID_NUMBER']:
		agentname = "0011"
	else:
		agentname = phonenumber[9:]
	# fix this to better scramble and actually check if the agent name is taken
	r = lambda: random.randint(0,255)
	printcolor = '#%02X%02X%02X'%(r(),r(),r())
	# random color from http://stackoverflow.com/questions/13998901/generating-a-random-hex-color-in-python
	name = content
	# fiddle with this as well
	players.insert({
		"name": name,
		"agentname": agentname,
		"score": 0,
		"printcolor": printcolor,
		"phonenumber": phonenumber
		})


def getAgentName(phonenumber, content):
	# players.find for player, based on phone number
	# return player agent name
	agentname = players.find({"phonenumber":phonenumber}, {"agentname":1, "_id":0})[0]["agentname"]
	if agentname is None:
		agentname = newPlayer(phonenumber, content)
	return agentname


#----------App routing-------------------

@app.route('/', methods=['GET'])
def index():
	return "Sekkrits"

@app.route('/leaconsole', methods=['GET'])
def console():
	return render_template("template.html", information = transcript)

@app.route('/leaconsole', methods=['POST'])
def consolesend():
	sendtonumber = request.form.get('To', None)
	content = request.form.get('Body', "empty text?")
	try:
		message = twilioclient.sms.messages.create(body=content, to=sendtonumber, from_=twilionumber)
 	except twilio.TwilioRestException as e:
 		print e
 		return e
	return render_template("template.html", information = transcript)


@app.route('/twilio', methods=['POST'])
def incomingSMS():
	phonenumber = request.form.get('From', None)
	content = request.form.get('Body', "empty text?")
	agent = getAgentName(phonenumber, content)

	sendToRecipient(content = "Hello, "+agent, recipient = agent, sender = "HQ")
 	
 	return "Success"


#-----------Run it!----------------------

if __name__ == "__main__":
	app.run(debug=debug)
