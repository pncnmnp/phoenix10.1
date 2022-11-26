# Note: brew install ffmpeg
# Note: brew install espeak

import datetime
import glob
import json
import random
import re
import os
from pathlib import Path


import feedparser
import ffmpy
import nltk
from pydub import AudioSegment
import requests
import ytmdl

from TTS import __file__ as tts_path
from TTS.tts.utils.text.cleaners import english_cleaners
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer
from TTS.server.server import create_argparser


# Dependencies
# nltk.download("punkt")


class Recommend:
    def __init__(self):
        self.ad_prob = 1
        self.question = None

    def news_urls(self, category):
        urls = {
            "world": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "business": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
            "technology": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
            "science": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
        }
        return urls[category]

    def news(self, category="world", k=5):
        paper = feedparser.parse(self.news_urls(category))
        info = []
        for source in paper.entries[:k]:
            info += [source["title"] + ". " + source["summary"]]
        return info

    def person(
        self,
        fname="./data/fnames.txt",
        lname="./data/lnames.txt",
        locdata="./data/locdata.txt",
    ):
        with open(fname, "r", encoding="UTF-8") as f:
            first = random.choice(f.readlines()).strip()
        with open(lname, "r", encoding="UTF-8") as f:
            last = random.choice(f.readlines()).strip()
        with open(locdata, "r", encoding="UTF-8") as f:
            loc = random.choice(f.readlines()).strip().split(" ")[0]
        return first, last, loc

    def daily_question(self, file="./gpt/daily_question.json", question=True):
        # Questions from https://github.com/ParabolInc/icebreakers/blob/main/lib/api.ts
        if question:
            with open(file, "r", encoding="UTF-8") as f:
                questions = json.load(f)
                self.question = random.choice(list(questions.keys()))
                return self.question
        else:
            with open(file, "r", encoding="UTF-8") as f:
                questions = json.load(f)
                response = random.choice(questions[self.question])
                self.question = False  # indicates that question has been answered
                return response

    def advertisement(self, file="./gpt/ads.json"):
        # From https://en.wikipedia.org/wiki/Category:Fictional_companies
        prob = random.random()
        if prob <= self.ad_prob:
            with open(file, "r", encoding="UTF-8") as f:
                ads = json.load(f)
            self.ad_prob /= 4
            return random.choice(ads)
        return None

    def weather(self, location):
        r = requests.get(f"https://wttr.in/{location}?format=j1", timeout=100)
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
        r = requests.get(url, timeout=100)
        events = [event["text"] for event in r.json()["events"]]
        facts = sorted(events, key=lambda fact: len(fact))[:k]
        return facts


class Dialogue:
    def __init__(self, file="./schema.json"):
        self.rec = Recommend()
        self.synthesizer = self.init_speech()
        with open(file, "r", encoding="UTF-8") as f:
            self.schema = json.load(f)
        self.index = 0

    def wakeup(self):
        now = datetime.datetime.now()
        speech = (
            "You are tuning into Phoenix ten point one! "
            "I am your host Charlie. "
            f"It is {now.hour} {now.minute} in my studio and "
            "I hope that you are having a splendid day so far!"
        )
        return speech

    def sprinkle_gpt(self):
        speech = self.rec.advertisement()
        if speech is not None:
            return speech
        if self.rec.question is None:
            ques = self.rec.daily_question()
            speech = (
                "And now it is time for today's daily question! "
                f"Are you Ready? Alright! Today's question is - {ques} "
                "You can post your answers on Twitter, hashtag phoenix ten point one, "
                "and we will read it on air. "
            )
            return speech
        if self.rec.question:
            ans = self.rec.daily_question(question=False)
            fname, lname, loc = self.rec.person()
            speech = (
                "Wow! Seems like your answers to our daily question are rolling in. "
                f"My favorite is from {fname} {lname} from {loc}. "
                f"They say that - {ans}"
                f" That was a fun one! Thank you {fname}! "
            )
            return speech

    def over(self):
        speech = (
            "And that's it for today's broadcast! "
            "Thanks for listening to Phoenix ten point one! "
            "Hope you have a great day ahead! Bye Bye! "
        )
        return speech

    def news(self, category, k):
        articles = self.rec.news(category, k)
        start = f"Now for today's {category} news. "
        end = f"And that's the {category} news."
        filler = [". In another news, ", ". Yet another news, ", ". A latest update, "]
        speech, choice_index = start, 0
        for article in articles:
            speech += article + filler[choice_index % len(filler)]
            choice_index += 1
        return speech[: -len(filler[(choice_index - 1) % len(filler)])] + end

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

    def music_meta(self, song, start=True):
        info = ytmdl.metadata.get_from_itunes(song)[0].json
        if start:
            speech = (
                f'The next song is from the world of {info["primaryGenreName"]}. '
                f'{info["trackName"]} by {info["artistName"]}. '
            )
            return speech
        else:
            speech = (
                f'That was {info["trackName"]} by {info["artistName"]}. '
                "You are listening to Phoenix ten point one! "
            )
            return speech

    def flow(self):
        for action, meta in self.schema:
            speech = None
            match action:
                case "up":
                    speech = self.wakeup()
                    self.speak(speech, announce=True)
                    speech = self.sprinkle_gpt()
                    self.speak(speech)
                case "music":
                    for song in meta:
                        speech = self.music_meta(song)
                        self.speak(speech, announce=True)
                        self.music(song)
                        speech = self.music_meta(song, start=False)
                        self.speak(speech, announce=True)
                        speech = self.sprinkle_gpt()
                        self.speak(speech)
                case "news":
                    category, k = meta
                    speech = self.news(category, k)
                    self.speak(speech)
                case "weather":
                    speech = self.weather(meta)
                    self.speak(speech)
                case "fun":
                    speech = self.on_this_day()
                    self.speak(speech)
                case "end":
                    speech = self.over()
                    self.speak(speech, announce=True)
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
        base.export(outfile, format="wav")

    def cleaner(self, speech):
        abbreviations = {
            "a": "ae",
            "b": "bee",
            "c": "sieh",
            "d": "dea",
            "e": "ee",
            "f": "F.",
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
        acronyms = re.findall("[A-Z](?:[\\.&]?[A-Z]){1,7}[\\.]?|[A-Z][\\.]", speech)
        for acronym in acronyms:
            cleaned_up = acronym.replace(".", "")
            pronounce = str()
            for alphabet in cleaned_up:
                pronounce += abbreviations[alphabet.lower()] + " "
            speech = speech.replace(acronym, pronounce.replace(".", ""))
        return english_cleaners(
            speech.replace("..", ".").replace("’", "'").replace(".,", ",")
        )

    def speak(self, speech, announce=False):
        if speech is None:
            return
        speeches = nltk.sent_tokenize(speech)
        say = str()
        start_file_index = self.index
        for speech in speeches:
            curr = say + speech
            if len(curr) > 200:
                self.save_speech(self.cleaner(say))
                say = str()
            say += speech + " "
        self.save_speech(say)
        if announce:
            self.background_music()
        else:
            self.slow_it_down(start_file_index)
        self.silence()

    def slow_it_down(self, start_index):
        for index in range(start_index, self.index):
            src = f"./temp/a{index}.wav"
            dest = "./temp/out.wav"
            slowit = ffmpy.FFmpeg(
                global_options=["-y"],
                inputs={src: None},
                outputs={dest: ["-filter:a", "atempo=0.9"]},
            )
            slowit.run()
            # FFmpeg cannot edit existing files in-place
            os.remove(src)
            os.rename(dest, src)

    def background_music(self, file="./data/loboloco.wav"):
        background = AudioSegment.from_wav(file)
        background -= 25  # reduce the volume
        speech = AudioSegment.from_wav(f"./temp/a{self.index - 1}.wav")
        imposed = background.overlay(speech, position=4000)
        imposed.export(f"./temp/a{self.index - 1}.wav", format="wav")

    def silence(self):
        no_audio = AudioSegment.silent(duration=2000)
        no_audio.export(f"./temp/a{self.index}.wav", format="wav")
        self.index += 1

    def init_speech(self):
        args = create_argparser().parse_args()
        args.model_name = "tts_models/en/vctk/vits"
        path = Path(tts_path).parent / "./.models.json"
        manager = ModelManager(path)
        model_path, config_path, model_item = manager.download_model(args.model_name)
        args.vocoder_name = (
            model_item["default_vocoder"]
            if args.vocoder_name is None
            else args.vocoder_name
        )
        synthesizer = Synthesizer(
            tts_checkpoint=model_path,
            tts_config_path=config_path,
            tts_speakers_file=None,
            tts_languages_file=None,
            vocoder_checkpoint=None,
            vocoder_config=None,
            encoder_checkpoint="",
            encoder_config="",
            use_cuda=args.use_cuda,
        )
        return synthesizer

    def save_speech(self, text):
        wavs = self.synthesizer.tts(text, speaker_name="p267", style_wav="")
        self.synthesizer.save_wav(wavs, f"./temp/a{self.index}.wav")
        self.index += 1


if __name__ == "__main__":
    dialogue = Dialogue()
    dialogue.flow()
