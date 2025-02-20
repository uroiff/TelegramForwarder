# Telegram Message Forwarder

This script is designed to automatically forward messages from some specified Telegram channels or chats to a target group. It offers powerful filtering capabilities based on keywords and/or number.


## 📚 Features

|Feature																|Supported    |
|---------------------------------------|-------------|
|Support multiple sessions  						| ✅   				|
|Support multiple sources/destinations 	| ✅   				|
|Support for telethon .session 					| ✅   				|
|Filter message by keyword  						| ✅   				|
|Filter message by comparing number			| ✅  				|

## ⚙ Settings

|Setting										|Description                                          |
|---------------------------|-----------------------------------------------------|
|api_id/api_hash						|Platform data from which to run the Telegram session |
|sessions										|List of Telegram sessions  													|
|source											|Username of the bot or channel  											|
|destination								|URL of the destination group  												|
|keyword_filtering_enabled	|Toggle to enable keyword filtering  									|
|keywords_include						|Keywords that MUST be included in the message  			|
|keywords_exclude						|Keywords that MUST be excluded from the message  		|
|number_threshold_enabled		|Toggle to enable filtering by number threshold 			|
|number_threshold_min				|Minimum number  																			|
|number_threshold_max				|Maximum number  																			|
|number_regex_patterns			|Regular expressions to process numbers  							|

## 📌 Prerequisites 

Before you start, make sure you have the following installed:
* Python version 3.10 or 3.11. 
[![Contact](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue)](https://www.python.org/downloads/)

## ⚡ Quick Start

1. Clone the repository to your server.
2. Install the necessary dependencies.
3. Create your sessions or use your existing sessions.
4. Edit the config.json file according to your needs.
	* For multiple sessions, please add the session name in *sessions*.
	* To handle multiple sources/destination, create more items in *mappings* array.
5. Run python main.py to start.

## 📃 Getting Credentials

1.  Go to [my.telegram.org](https://my.telegram.org) and log in using your phone number.
2.  Select **"API development tools"** and fill out the form to register a new application.
3.  Record the `API_ID` and `API_HASH`, provided after registering your application.

## 💬 Contacts 
For support or questions, contact me on Telegram:
 [![Contact](https://img.shields.io/badge/Telegram-%40Me-orange)](https://t.me/fiorume)
