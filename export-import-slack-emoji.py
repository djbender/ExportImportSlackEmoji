#!/usr/bin/env python

import requests
import json
import re
import os
import time
import re
from os import walk

# --------------------------------------
# Set these 4 values then run the script 
# -------------------------------------
sourceSlackOrgCookie = ''
sourceSlackOrgToken = ''
destinationSlackOrgCookie = ''
destinationSlackOrgToken = ''

emojiDownloadFolder = 'slackEmoji'
sourceSlackOrgHeaders = {'cookie': sourceSlackOrgCookie, 'Authorization' : f'Bearer {sourceSlackOrgToken}'}
destinationSlackOrgHeaders = {'cookie': destinationSlackOrgCookie, 'Authorization' : f'Bearer {destinationSlackOrgToken}'}

if not os.path.exists(emojiDownloadFolder):
    os.makedirs(emojiDownloadFolder)

existingEmojiFileNames = []
for (dirpath, dirnames, filenames) in walk(emojiDownloadFolder):
    existingEmojiFileNames.extend(filenames)
    break

def getEmojiNameToUrlDict(headers):
    url = 'https://slack.com/api/emoji.list'
    response = requests.get(url, headers=headers)

    responseJson = json.loads(response.content)
    emojiNameToUrlDict = responseJson["emoji"]

    return emojiNameToUrlDict

# ----------------
# Do the downloading
# ----------------

emojiNameToUrlDict = getEmojiNameToUrlDict(sourceSlackOrgHeaders)

for emojiName in emojiNameToUrlDict:
     
    emojiUrl = emojiNameToUrlDict[emojiName]
    if not emojiUrl.startswith('alias:'):
        
        emojiFileExtension = re.search('\.\w+$', emojiUrl).group()

        emojiFileName = f'{emojiName}{emojiFileExtension}'

        if emojiFileName in existingEmojiFileNames:
            print(f'Emoji {emojiName}{emojiFileExtension} already downloaded, skipping download')
            continue

        response = requests.get(emojiUrl)

        # Write the resposne to a file
        invalidFileNameCharatersRegex = ':|;'
        emojiFileName = f'{emojiDownloadFolder}/{emojiName}{emojiFileExtension}'
        emojiFileName = re.sub(invalidFileNameCharatersRegex, '_', emojiFileName)
        open(emojiFileName, 'wb').write(response.content)

        print(f'Saved {emojiFileName}')

# ----------------
# Do the uploading
# ----------------

# get the existing emoji so we scan skip trying to upload any already existing emoji
destinationEmojiNameToUrlDict = getEmojiNameToUrlDict(destinationSlackOrgHeaders)

url = 'https://slack.com/api/emoji.add'

def printProgress(position, total, msg):
    print(f'[{position}/{total}] {msg}')

existingEmojiFileNames.sort()
for emojiFileName in existingEmojiFileNames:
    position = existingEmojiFileNames.index(emojiFileName)
    total = len(existingEmojiFileNames)
    progress = '{position}/{total}'

    emojiFileNameWithoutExtension = emojiFileExtension = re.search('([^\.]+)\.', emojiFileName).group(1)

    if emojiFileNameWithoutExtension in destinationEmojiNameToUrlDict:
        printProgress(position, total, f'Emoji already exits in destination, skipping upload: "{emojiFileNameWithoutExtension}"')
        continue

    emojiUploaded = False

    while (not emojiUploaded):

        payload = {
            'mode': 'data',
            'name': emojiFileNameWithoutExtension
        }

        files = [
            ('image', open(f'slackEmoji/{emojiFileName}','rb'))
        ]

        response = requests.request("POST", url, headers=destinationSlackOrgHeaders, data = payload, files = files)

        responseJson = json.loads(response.content)

        if responseJson["ok"]:
            printProgress(position, total, f'Uploaded {emojiFileName}')
            emojiUploaded = True
        elif not responseJson["ok"] and responseJson["error"] == "error_name_taken":
            printProgress(position, total, f'Emoji already exits in destination, skipping upload: "{emojiFileNameWithoutExtension}"')
            emojiUploaded = True
        elif not responseJson["ok"] and responseJson["error"] == "error_name_taken_i18n":
            printProgress(position, total, f'Emoji already exits in destination, skipping upload: "{emojiFileNameWithoutExtension}"')
            emojiUploaded = True
        elif not responseJson["ok"] and responseJson["error"] == "ratelimited":
            retryAfter = int(response.headers['retry-after'])
            printProgress(position, total, f'Exceeded rate limit, waiting {retryAfter} seconds before retrying')
            time.sleep(retryAfter)
        else:
            printProgress(position, total, f'Unexpected failure! {responseJson["error"]}')
            printProgress(position, total, response)
            printProgress(position, total, response.headers)
            printProgress(position, total, response.json)
            break

        # this endpoint is a Tier 2 rate limited api, which means it can execute 20 times per
        # minute without throttling. Instead of hitting the rate limit each time, we can
        # instead insert a sleep here of three seconds to then never need to retry. This is
        # however left out as a default in case the API Tiering rules change.
        # time.sleep(3)
