cocktailgames
=============

A spy-themed party game using Twilio and Flask.  Participants send a text to the registered Twilio number to join; during the game, they are assigned spy tasks via SMS and attempt to discover the identities of other spies.  Subterfuge ensues.

Twilio routes incoming SMS messages to a POST request to the game's URL, where it is handled by the Flask app. Outgoing messages are sent with [Twilio's python wrapper](https://github.com/twilio/twilio-python).

See [this post](http://instamatique.com/hackerschool/blog/2013/11/11/project-writeup-spy-game/) for further information about the development and beta test of the game.
