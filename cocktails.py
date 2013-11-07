from flask import *
import twilio.twiml
from twilio.rest import TwilioRestClient
import os 
from pymongo import *
import datetime
import random
import re

debug = False
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

def lookup(collection, field, fieldvalue, response):
	if response:
		return collection.find({field:fieldvalue}, {response:1, "_id":0})[0][response] 
	else:
		return collection.find({field:fieldvalue})

def sendToRecipient(content, recipient, sender="HQ"):
	recipientnumber = lookup(collection=players, field="agentname", fieldvalue=recipient, response="phonenumber")
	recipientcolor = lookup(collection=players, field="agentname", fieldvalue=recipient, response="printcolor")
	# recipientnumber = players.find({"agentname":recipient}, {"phonenumber":1, "_id":0})[0]["phonenumber"] 
	#theory: "find" returns an array of objects; the first one ought to be the one we want
	sendernumber = twilionumber
	time = datetime.datetime.now() #function here to return time
	
	try:
		message = twilioclient.sms.messages.create(body=content, to=recipientnumber, from_=twilionumber)
		transcript.insert({"time":time, "sender":sender, "recipient":recipient, "content":content, "color":recipientcolor, "error":"no"})
 	except twilio.TwilioRestException as e:
 		transcript.insert({"time":time, "sender":sender, "recipient":recipient, "content":content, "color":recipientcolor, "error":e})




def newPlayer(phonenumber, content):
	# generate agent name
	# add name, agent, init points, etc to players collection
	if phonenumber == os.environ['DAVID_NUMBER']:
		agentname = "0011"
	else:
		agentname = "0"+str(random.randint(10,99))
		# fix this to better scramble and actually check if the agent name is taken
		while players.find({"agentname": agentname}).count() > 0:
			agentname = "0"+str(random.randint(10,99))
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
	greet(agentname)
	return agentname


def getAgentName(phonenumber, content):
	# players.find for player, based on phone number
	# return player agent name
	if players.find({"phonenumber": phonenumber}).count() == 0:
		agentname = newPlayer(phonenumber, content)
	else:
		agentname = lookup(collection=players, field="phonenumber", fieldvalue=phonenumber, response="agentname")
	return agentname


def greet(agentname):
	sendToRecipient(content = "Hello, Agent "+agentname+"! Your skills will be vital to the success of this event. To abandon the event before its completion, txt \"end.\" Await further instruction.", recipient = agentname, sender = "HQ")

def assignWords(collection):
	pass
	# set player's tasks to a list of words and send them intro message


def retireAgent(agentname):
	pass
	# set player's Active to false and send goodbye message

def gameLogic(agentname, content):
	print "gamelogic!"
# if the content begins with a number, route the content through to the other agent
	agentnamematch = re.match("\d{3,4}", content)
	helpmatch = re.match("help", content)
	reportmatch = re.match("report", content.lower())
# if first word is digits of an agent name, forward the message
	if agentnamematch:
		recipient = agentnamematch.group(0)
		if players.find({"agentname": recipient}).count() == 0:
			sendToRecipient(content = "There is no such agent.", recipient = agentname, sender = "HQ")
		else:
			content = re.sub("\d{3,4}", "From "+agentname, content)
			sendToRecipient(content = content, recipient = recipient, sender = agentname)
			print "Direct message to "+recipient+": "+content
	elif helpmatch:
		helptext = ""
		# if we are in directmessaging:
		helptext = helptext+"To message another agent, use \"[their number]: [message]\"\n"
		# if we are in reporting:
		helptext = helptext+"To report a piece of intelligence, txt \"report: [the word]\""
		sendToRecipient(content = helptext, recipient = agentname, sender = "HQ")
	elif endmatch:
		retireAgent(agentname)

# if the content is an intel word, figure out whose intel words they could be and answer with that
	elif reportmatch:
		textinput = re.sub("report:\s*", "", content.lower())
		textinput = re.sub("[^a-z\s]", "", textinput)
		# convert input to lower, strip out punctuation and numbers
		agentNamesAndTasks = players.find({"active":True}, {"agentname":1, "tasks":1 "_id":0}) 
		potentialagents = []
		for player in agentNamesAndTasks:
			for word in player.tasks:
				if word == content:
					potentialagents.add(player.agentname)
		if len(potentialagents) > 0:
			message = "Our records show that the observed agent could be Agent "+potentialagents.join(" or ")+"."
		else:
			message = "Our records do not show evidence of any such intelligence."
		sendToRecipient(content = message, recipient=agentname, sender = "HQ")

	else:
		print "didn't match"
		pass

# if the content is an intel word, figure out whose intel words they could be and answer with that
# 
# when the "assign words" trigger is pulled, each player is assigned two words to slip into a conversation
# and warned that enemy agents are also using code words
# 

# 	
	


#----------App routing-------------------

@app.route('/', methods=['GET'])
def index():
	return "Sekkrits"

@app.route('/leaconsole', methods=['GET'])
def console():
	return render_template("template.html", information = transcript)

@app.route('/leaconsole', methods=['POST'])
def consoleSend():
	agentname = request.form.get('To', None)
	content = request.form.get('Body', "empty text?")
	
	sendToRecipient(content = content, recipient = agentname, sender = "HQ")

	return render_template("template.html", information = transcript)


@app.route('/twilio', methods=['POST'])
def incomingSMS():
	fromnumber = request.form.get('From', None)
	content = request.form.get('Body', "empty text?")
	agentname = getAgentName(fromnumber, content)
	agentcolor = lookup(collection=players, field="agentname", fieldvalue=agentname, response="printcolor")
	time = datetime.datetime.now()
	transcript.insert({"time":time, "sender":agentname, "recipient":"HQ", "content":content, "color":agentcolor, "error":"no"})

	gameLogic(agentname, content)


	return "Success"


#----------Jinja filter-----------------
@app.template_filter('printtime')
def timeToString(timestamp):
    return str(timestamp)[11:16]



#-----------Run it!----------------------

if __name__ == "__main__":
	app.run(debug=debug)
