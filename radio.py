# Note: brew install ffmpeg

import datetime
import subprocess
import json
import random
import os
import glob
import re

import nltk
import requests
import feedparser
from pydub import AudioSegment
from TTS.tts.utils.text.cleaners import english_cleaners
import ytmdl

# Dependencies
# nltk.download("punkt")


class Recommend:
    def __init__(self):
        pass

    def news_urls(self, category):
        urls = {
            "world": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "business": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
            "technology": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        }
        return urls[category]

    def news(self, category="world", k=5):
        paper = feedparser.parse(self.news_urls(category))
        info = list()
        for source in paper.entries[:k]:
            info += [source["summary"]]
        return info

    def weather(self, location):
        r = requests.get(f"https://wttr.in/{location}?format=j1")
        forecast = r.json()["current_condition"][0]
        rain = r.json()["weather"][0]["hourly"][0]["chanceofrain"]
        summary = {
            "weather": forecast["weatherDesc"][0]["value"],
            "c": forecast["temp_C"],
            "f": forecast["temp_F"],
            "rain": rain,
            "cloudcover": forecast["cloudcover"],
            "windspeedKmph": forecast["windspeedKmph"],
        }
        return summary

    def on_this_day(self, k=5):
        now = datetime.datetime.now()
        month, day = now.month, now.day
        url = f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/{month}/{day}"
        r = requests.get(url)
        events = [event["text"] for event in r.json()["events"]]
        facts = sorted(events, key=lambda fact: len(fact))[:k]
        return facts


class Dialogue:
    def __init__(self, file="./schema.json"):
        self.rec = Recommend()
        self.schema = json.load(open(file, "r"))
        self.index = 0

    def wakeup(self):
        now = datetime.datetime.now()
        speech = (
            "Greetings! "
            f"It is {now.hour} O clock at the time of this recording. "
            "Whenever you are listening to this, I hope you are doing splendid! Let's start this day with some music shall we?"
        )
        return speech

    def news(self, category, k):
        articles = self.rec.news(category, k)
        start = f"Now for today's {category} news. "
        filler = [". In another news, ", ". Yet another news, ", ". A latest update, "]
        speech, choice_index = start, 0
        for article in articles:
            speech += article + filler[choice_index % len(filler)]
            choice_index += 1
        return speech[: -len(filler[(choice_index - 1) % len(filler)])]

    def weather(self, location):
        forecast = self.rec.weather(location)
        speech = (
            f'It seems like the weather today is going to be {forecast["weather"]}. '
            f'Presently, it is {forecast["c"]} degree celcius and {forecast["f"]} degree fahrenheit. '
            f'There seems to be a {forecast["rain"]} percent chance of rain in the next hour. '
            f'The cloud cover is {forecast["cloudcover"]} percent with a wind speed of {forecast["windspeedKmph"]} kilo-meters per hour. '
        )
        return speech

    def on_this_day(self):
        fact = random.choice(self.rec.on_this_day(5))
        speech = f"Fun fact! On this day {fact}"
        return speech

    def music(self, song):
        args = ytmdl.main.arguments()
        args.SONG_NAME = [song]
        args.choice = 1
        args.quiet = True
        ytmdl.defaults.DEFAULT.SONG_DIR = "./temp/"
        ytmdl.main.main(args)

        # Logic to change name
        # ytmdl does not natively support this feature
        mp3 = glob.glob(os.path.join("./temp/", "*.mp3"))[0]
        sound = AudioSegment.from_mp3(mp3)
        sound.export(f"./temp/a{self.index}.wav", format="wav")
        os.remove(mp3)
        self.index += 1

    def music_meta(self, song):
        info = ytmdl.metadata.get_from_itunes(song)[0].json
        speech = (
            f'The next song is from the world of {info["primaryGenreName"]}. '
            f'{info["trackName"]} by {info["artistName"]}. '
        )
        return speech

    def flow(self):
        for action, meta in self.schema:
            speech = None
            match action:
                case "up":
                    speech = self.wakeup()
                    self.speak(speech)
                case "music":
                    for song in meta:
                        speech = self.music_meta(song)
                        self.speak(speech)
                        self.music(song)
                case "news":
                    category, k = meta
                    speech = self.news(category, k)
                    self.speak(speech)
                case "weather":
                    speech = self.weather("Raleigh")
                    self.speak(speech)
                case "fun":
                    speech = self.on_this_day()
                    self.speak(speech)
                case _:
                    pass
        self.radio()
        return 0

    def radio(self):
        infiles = [
            AudioSegment.from_file(f"./temp/a{i}.wav") for i in range(self.index)
        ]
        outfile = "radio.wav"
        base = infiles.pop(0)
        for infile in infiles:
            base = base.append(infile)
        file_handle = base.export(outfile, format="wav")

    def cleaner(self, speech):
        abbreviations = {
            "a": "ay",
            "b": "bee",
            "c": "sieh",
            "d": "dea",
            "e": "ee",
            "f": "eff",
            "g": "jie",
            "h": "edge",
            "i": "eye",
            "j": "jay",
            "k": "kaye",
            "l": "elle",
            "m": "emme",
            "n": "en",
            "o": "owe",
            "p": "pea",
            "q": "queue",
            "r": "are",
            "s": "esse",
            "t": "tea",
            "u": "hugh",
            "v": "vee",
            "w": "doub you",
            "x": "ex",
            "y": "why",
            "z": "zee",
            "1": "one",
            "2": "two",
            "3": "three",
            "4": "four",
            "5": "five",
            "6": "six",
            "7": "seven",
            "8": "eight",
            "9": "nine",
            "0": "zero",
        }
        # Regex from https://stackoverflow.com/a/53149449 by SQB
        # Licensed under CC BY-SA 4.0
        acronyms = re.findall("\\b[A-Z](?:[\\.&]?[A-Z]){1,7}\\b", speech)
        for acronym in acronyms:
            cleaned_up = acronym.replace(".", "")
            pronounce = str()
            for alphabet in cleaned_up:
                pronounce += abbreviations[alphabet.lower()] + " "
            speech = speech.replace(acronym, pronounce)
        return english_cleaners(speech.replace("..", ".").replace("’", "'"))

    def speak(self, speech):
        if speech == None:
            return
        speeches = nltk.sent_tokenize(speech)
        say = str()
        for speech in speeches:
            curr = say + speech
            if len(curr) > 200:
                self.save_speech(self.cleaner(say))
                say = str()
            say += speech + " "
        self.save_speech(say)

    def save_speech(self, text):
        subprocess.run(
            [
                "tts",
                "--text",
                text,
                "--model_name",
                "tts_models/en/ljspeech/tacotron2-DDC",
                "--out_path",
                f"./temp/a{self.index}.wav",
            ]
        )
        self.index += 1


if __name__ == "__main__":
    dialogue = Dialogue()
    dialogue.flow()
