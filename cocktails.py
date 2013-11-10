# Happy birthday to David.

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
games = database["games"]


# ----------Function Defs-------------------------------------------
# --------Helpers--------
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
		transcript.insert({"time":time, "sender":sender, "recipient":recipient, "content":content, "color":recipientcolor})
 	except twilio.TwilioRestException as e:
 		content = content+" with error: "+e
 		transcript.insert({"time":time, "sender":sender, "recipient":recipient, "content":content, "color":recipientcolor})
 	return

def numberOfPlayers():
	return players.find({"active":"True"}, {"agentname":1, "_id":0}).count()


# -----Game functions------
def getAgentName(phonenumber, content):
	# players.find for player, based on phone number
	# return player agent name
	if players.find({"phonenumber": phonenumber}).count() == 0:
		agentname = newPlayer(phonenumber, content)
	else:
		agentname = lookup(collection=players, field="phonenumber", fieldvalue=phonenumber, response="agentname")
	return agentname


def newPlayer(phonenumber, content):
	r = lambda: random.randint(0,255)
	printcolor = '#%02X%02X%02X'%(r(),r(),r())
	# random color from http://stackoverflow.com/questions/13998901/generating-a-random-hex-color-in-python
	name = content
	# fiddle with this as well
	factionlist = lookup(games, "active", "True", "affiliations")
	affiliation = factionlist[random.randint(0, len(factionlist)-1)]
	#generate affiliation
	if phonenumber == mynumber:
		agentname = "Q"
		printcolor = '#008080'
	else:
		agentname = "0"+str(random.randint(10,99))
		while players.find({"agentname": agentname}).count() > 0:
			agentname = "0"+str(random.randint(10,99))
	# generate agent name
	# add name, agent, init points, etc to players collection
	players.insert({
		"agentname": agentname,
		"phonenumber": phonenumber,
		"printcolor": printcolor,
		"active": "True",
		"task": [],
		"affiliation": affiliation,
		"successfulTransmits":[],
		"interceptedTransmits":[],
		"reportedEnemies":[],
		"spuriousReports":[],
		"name": name,
		"knowsaboutmissions":"False",
		"squelchgamelogic":"True"
		})
	greet(agentname)
	if phonenumber == os.environ['DAVID_NUMBER']:
			birthdaymessage = os.environ['BIRTHDAY_MESSAGE']
			sendToRecipient(content = birthdaymessage, recipient = agentname, sender = "Q")
	return agentname


def greet(agentname):
	message = "Hello, Agent "+agentname+"! Your skills will be vital to the success of this event. To abandon the event before its completion, txt \"leaving.\" Await further instruction."
	sendToRecipient(content = message, recipient = agentname, sender = "HQ")
	return

def retireAgent(agentname):
	players.update({"agentname":agentname}, {"$set": {"active":"False"}})
	print "updated player to inactive"
	sendToRecipient(content = "Good work and goodbye, Agent "+agentname+"!", recipient = agentname, sender = "HQ")
	return

def helpAgent(agentname):
	pass
	print "helpmatch!"
	helptext = ""
	if lookup(players, "agentname", agentname, "knowsaboutmissions") == "False":
		helptext = "Stand by."
	else:
		helptext = "To report a piece of intelligence, txt \"report: [the word]\""
	if lookup(games, "active", "True", "directmessaging") == "True":
		helptext = "To message another agent, use \"[their number]: [message]\"\n"+helptext
	sendToRecipient(content = helptext, recipient = agentname, sender = "HQ")	
	return

def makeReport(reportingagent, report):
	reportingagentteam = lookup(players, "agentname", reportingagent, "affiliation")
	for player in players.find({"active":"True"}, {"agentname":1, "affiliation":1, "task":1, "_id":0}):
		if len(player["task"])>0:
			if report == player["task"][-1]:
				reportedagent = player["agentname"]
				reportedagentteam = player["affiliation"]
				if reportedagent == reportingagent:
					message = "Our records show that the only agent assigned to code \""+report+"\" is you."
					sendToRecipient(content = message, recipient=reportedagent, sender = "HQ")
					return
				elif reportingagentteam == reportedagentteam:
					players.update({"agentname":reportedagent}, {"$push":{"successfulTransmits":report}})
					message = "Our Agent "+reportingagent+" has reported your successful transmission of the code \""+report+"\" -- good work!"
					sendToRecipient(content = message, recipient=reportedagent, sender = "HQ")
					return
				else:
					players.update({"agentname":reportingagent}, {"$push":{"reportedEnemies":reportedagent}})
					players.update({"agentname":reportedagent}, {"$push":{"interceptedTransmits":report}})
					message = "Sources have confirmed the reception of your code \""+report+"\" by enemy agent "+reportingagent+"! Be more careful."
					sendToRecipient(content = message, recipient=reportedagent, sender = "HQ")
					return
	# if it turns out the report was spurious
	games.update({"active":"True"}, {"$push":{"spuriousReports":report}})
	players.update({"agentname":reportingagent}, {"$push":{"spuriousReports":report}})
	sendToRecipient(content = "Our records do not show evidence of any such intelligence.", recipient=reportingagent, sender = "HQ")
	return


# --------Game Events---------
def assignWords():
	# set player's tasks to a list of words and send them intro message
	wordlist = lookup(games, "active", "True", "wordlist")
	for player in players.find({"active":"True"}, {"agentname":1, "task":1, "knowsaboutmissions":1, "_id":0}):
		word = wordlist[random.randint(0,len(wordlist)-1)]
		wordlist.remove(word)
		agentname = player["agentname"]
		players.update({"agentname":agentname}, {"$push": {"task":word}})
		if player["knowsaboutmissions"] == "False":
			message = "Mission: insert code \""+word+"\" unobtrusively into conversation. Use code frequently to ensure reception by our agents, but avoid detection by enemies."
			sendToRecipient(content = message, recipient = agentname, sender = "HQ")
			message = "Enemy agents will be using similar tactics! Report friendly or hostile intelligence by txting \"Report: [the word]\""
			sendToRecipient(content = message, recipient = agentname, sender = "HQ")
			players.update({"agentname":player["agentname"]}, {"$set":{"knowsaboutmissions":"True"}})
		else:
			message = "Your new code is: \""+word+".\" Cease using outdated codes."
			sendToRecipient(content = message, recipient = agentname, sender = "HQ")
	games.update({"active":"True"}, {"$set":{"wordlist":wordlist}})
	games.update({"active":"True"}, {"$set":{"wordsassigned":"True"}})
	return
	
def announceCake():
	message = "Rendezvous in dining room. Announce the identity of an enemy agent to earn cake."
	for player in players.find({"active":"True"}, {"agentname":1, "_id":0}):
		agentname = player["agentname"]
		sendToRecipient(content = message, recipient = agentname, sender = "HQ")

def announce(announcement):
	for player in players.find({"active":"True"}, {"agentname":1, "_id":0}):
		agentname = player["agentname"]
		sendToRecipient(content = announcement, recipient = agentname, sender = "HQ")

def teachMessaging():
	message = "To send a message any other agent (friend or enemy), use \"[their number]: [message]\""
	for player in players.find({"active":"True"}, {"agentname":1, "_id":0}):
		agentname = player["agentname"]
		sendToRecipient(content = message, recipient = agentname, sender = "HQ")
	games.update({"active":"True"}, {"$set":{"directmessaging":"True"}})

def endParty():
	for player in players.find({"active":"True"}, {"agentname":1, "_id":0}):
		retireAgent(player["agentname"])



# ---------Game Logic!----------
def gameLogic(agentname, content):
	print "gamelogic!"
	if lookup(players, "agentname", agentname, "squelchgamelogic") == "True":
		players.update({"agentname":agentname}, {"$set":{"squelchgamelogic":"False"}})
		return
# if the content begins with a number, route the content through to the other agent
	agentnamematch = re.match("\d{3,4}", content)
	helpmatch = re.match("help", content.lower())
	reportmatch = re.match("report", content.lower())
	endmatch = re.match("leaving", content.lower())
	# hilariously, with the more natural-seeming "end," Twilio's own unsubscribe feature kicks in.
# if first word is digits of an agent name, forward the message
	if agentnamematch:
		print "agentnamematch!"
		recipient = agentnamematch.group(0)
		if players.find({"agentname": recipient}).count() == 0:
			sendToRecipient(content = "There is no such agent.", recipient = agentname, sender = "HQ")
		else:
			content = re.sub("\d{3,4}", "From "+agentname, content)
			sendToRecipient(content = content, recipient = recipient, sender = agentname)
			print "Direct message to "+recipient+": "+content
# if "help"
	elif helpmatch:
		helpAgent(agentname)
# if "end"
	elif endmatch:
		print "endmatch"
		retireAgent(agentname)
# if the content is an intel word, figure out whose intel words they could be and answer with that
	elif reportmatch:
		print "reportmatch!"
		textinput = re.sub("report:\s*", "", content.lower())
		textinput = re.sub("[^a-z\s]", "", textinput)
		# convert input to lower, strip out punctuation and numbers
		makeReport(agentname, textinput)
	else:
		helpAgent(agentname)
	return

def gameCommand(agentname, command):
	if command == "announce cake":
		print "announcing cake"
		announceCake()
	elif command == "assign words":
		print "assigning words"
		assignWords()
	elif command == "end party":
		endParty()
	elif command == "teach messaging":
		teachMessaging()
	elif agentname != "HQ":
		gameLogic(agentname,command)



#----------App routing-------------------------------------------

@app.route('/', methods=['GET'])
def index():
	return "Sekkrits"

@app.route('/leaderboard', methods=['GET'])
def leaderboard():
	spuriousList = lookup(games, "active", "True", "spuriousReports")
	return render_template("leaderboard.html", players = players, spuriousReports = spuriousList)

@app.route('/leaconsole', methods=['GET'])
def console():
	return render_template("console.html", information = transcript)

@app.route('/leaconsole/sentmessage', methods=['POST'])
def consoleSend():
	agentname = request.form.get('To', None)
	content = request.form.get('Body', "empty text?")
	sendToRecipient(content = content, recipient = agentname, sender = "HQ")

	return "<a href=\"/leaconsole\">back</a>"

@app.route('/leaconsole/sentcommand', methods=['POST'])
def consoleCommand():
	command = request.form.get('Command', None)
	gameCommand("HQ", command)
	return "<a href=\"/leaconsole\">back</a>"


@app.route('/leaconsole/sentannouncement', methods=['POST'])
def consoleAnnounce():
	announcement = request.form.get('Announcement', None)
	announce(announcement)
	return "<a href=\"/leaconsole\">back</a>"


@app.route('/twilio', methods=['POST'])
def incomingSMS():
	fromnumber = request.form.get('From', None)
	content = request.form.get('Body', "empty text?")
	agentname = getAgentName(fromnumber, content)
	agentcolor = lookup(collection=players, field="agentname", fieldvalue=agentname, response="printcolor")
	time = datetime.datetime.now()
	transcript.insert({"time":time, "sender":agentname, "recipient":"HQ", "content":content, "color":agentcolor})

	if agentname == lookup(games, "active", "True", "bootsontheground"):
		gameCommand(agentname, content)

	else:
		gameLogic(agentname, content)

	return "Success!"


#----------Jinja filter-------------------------------------------
@app.template_filter('printtime')
def timeToString(timestamp):
    return str(timestamp)[11:16]



#-----------Run it!----------------------------------------------

if __name__ == "__main__":
	app.run(debug=debug)
