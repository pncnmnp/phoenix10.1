"""
A private radio station with a personalized radio personality
Author: Parth Parikh (parthparikh1999p@gmail.com)
"""

# External dependencies required for the code below:
#   brew install ffmpeg
#   brew install espeak
# For sentence tokenization
#   nltk.download("punkt")

import datetime
import glob
import json
import random
import os
from pathlib import Path
import re
import uuid

from feedparser import parse
from ffmpy import FFmpeg
from nltk import sent_tokenize
from pydub import AudioSegment
import requests
import ytmdl

from TTS.server.server import create_argparser
from TTS.tts.utils.text.cleaners import english_cleaners
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer
from TTS import __file__ as tts_path

with open("./config.json", "r", encoding="UTF-8") as conf_file:
    CONF = json.load(conf_file)


class Recommend:
    """
    Recommends content for the radio personality
    """

    def __init__(self):
        self.ad_prob = 1
        self.question = None
        with open(CONF["rss"], "r", encoding="UTF-8") as file:
            self.rss_urls = json.load(file)

    def news(self, category="world", k=5):
        """
        Recommends news based on the news category
        """
        paper = parse(self.rss_urls[category])
        info = []
        for source in paper.entries[:k]:
            info += [source["title"] + ". " + source["summary"]]
        return info

    def person(self):
        """
        Provides a random identity -
            first name, last name, and place of residence
        Uses data from Linux's rig utility
        """
        with open(CONF["fname"], "r", encoding="UTF-8") as file:
            first = random.choice(file.readlines()).strip()
        with open(CONF["lname"], "r", encoding="UTF-8") as file:
            last = random.choice(file.readlines()).strip()
        with open(CONF["locdata"], "r", encoding="UTF-8") as file:
            loc = random.choice(file.readlines()).strip().split(" ")[0]
        return first, last, loc

    def daily_question(self, question=True):
        """
        Recommends a daily question and provides a realistic response
        Questions from
            https://github.com/ParabolInc/icebreakers/blob/main/lib/api.ts
        Responses from character.ai which seems to be using a variant of LaMDA
        """
        if question:
            with open(CONF["daily_ques"], "r", encoding="UTF-8") as file:
                questions = json.load(file)
                self.question = random.choice(list(questions.keys()))
                return self.question
        else:
            with open(CONF["daily_ques"], "r", encoding="UTF-8") as file:
                questions = json.load(file)
                response = random.choice(questions[self.question])
                # indicates that question has been answered
                self.question = False
                return response

    def advertisement(self):
        """
        Generates an advertisement
        Company names are fictional -
            https://en.wikipedia.org/wiki/Category:Fictional_companies
        GPT-2 was used to generate the responses
        GPT-2 phrase used was -
            Today's broadcast is sponsered by {company}.
            {company} is a {category} that is _
        """
        # From
        prob = random.random()
        if prob <= self.ad_prob:
            with open(CONF["ads"], "r", encoding="UTF-8") as file:
                ads = json.load(file)
            self.ad_prob /= 4
            company = random.choice(list(ads.keys()))
            return company, ads[company]
        return None, None

    def weather(self, location):
        """
        Fetches weather forecast
        """
        req = requests.get(f"https://wttr.in/{location}?format=j1", timeout=100)
        forecast = req.json()["current_condition"][0]
        rain = req.json()["weather"][0]["hourly"][0]["chanceofrain"]
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
        """
        Recommends an "On this day ....." using Wikipedia's MediaWiki API
        """
        now = datetime.datetime.now()
        month, day = now.month, now.day
        url = f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/all/{month}/{day}"
        req = requests.get(url, timeout=100)
        events = [event["text"] for event in req.json()["events"]]
        facts = sorted(events, key=lambda fact: len(fact))[:k]
        return facts


class Dialogue:
    """
    Generates and synthesizes speech for the radio personality
    Also, fetches music and its metadata
    """

    def __init__(self):
        self.rec = Recommend()
        self.synthesizer = self.init_speech()
        with open(CONF["schema"], "r", encoding="UTF-8") as file:
            self.schema = json.load(file)
        with open(CONF["phones"], "r", encoding="UTF-8") as file:
            self.phones = json.load(file)
        self.index = 0
        # Used to store intermediate audio clips
        self.audio_dir = "./" + uuid.uuid4().hex[:10]
        os.makedirs(self.audio_dir)

    def wakeup(self):
        """
        Routine to start the radio broadcast
        """
        now = datetime.datetime.now()
        period = "PM" if now.hour > 12 else "AM"
        hour = now.hour - 12 if now.hour > 12 else now.hour
        speech = (
            "You are tuning into Phoenix ten point one! "
            "I am your host Charlie. "
            f"It is {hour} {now.minute} {period} in my studio and "
            "I hope that you are having a splendid day so far!"
        )
        return speech

    def sprinkle_gpt(self):
        """
        Speech for advertisement and daily questions
        """
        speech, company = self.rec.advertisement()
        if speech is not None:
            end = f"Thank you {company} for sponsoring today's broadcast. "
            return speech + end
        if self.rec.question is None:
            ques = self.rec.daily_question()
            speech = (
                "And now it is time for today's daily question. "
                f"Are you Ready? Alright! Today's question is - {ques} "
                "You can post your answers on Twitter, hashtag phoenix ten point one, "
                "and we will read it on our broadcast. "
            )
            return speech
        if self.rec.question:
            ans = self.rec.daily_question(question=False)
            fname, lname, loc = self.rec.person()
            speech = (
                "Wow! Seems like your answers to our daily question are rolling in. "
                f"My favorite is from {fname} {lname} from {loc}. "
                f"They say that - {ans}"
                f" A great response! Thank you {fname}! "
            )
            return speech

    def over(self):
        """
        Routine to end the broadcast
        """
        speech = (
            "And that's it for today's broadcast! "
            "Thanks for listening to Phoenix ten point one! "
            "Hope you have a great day ahead! See You! "
        )
        return speech

    def news(self, category, k):
        """
        Speech to convey the daily news for a specific category
        """
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
        """
        Speech for the weather forecast
        """
        forecast = self.rec.weather(location)
        speech = (
            f'It seems like the weather today in {location} is going to be {forecast["weather"]}. '
            f'Presently, it is {forecast["c"]} degree celcius '
            f'and {forecast["f"]} degree fahrenheit. '
            f'There seems to be a {forecast["rain"]} percent chance of rain in the next hour. '
            f'The cloud cover is {forecast["cloudcover"]} percent '
            f'with a wind speed of {forecast["windspeedKmph"]} kilo-meters per hour. '
        )
        return speech

    def on_this_day(self):
        """
        Speech for the "On this day....." segment
        """
        fact = random.choice(self.rec.on_this_day(5))
        speech = f"Fun fact! On this day {fact}"
        return speech

    def music(self, song):
        """
        Fetches a song
        """
        args = ytmdl.main.arguments()
        args.SONG_NAME = [song]
        args.choice = 1
        args.quiet = True
        ytmdl.defaults.DEFAULT.SONG_DIR = self.audio_dir
        ytmdl.main.main(args)

        # Logic to change name
        # ytmdl does not natively support this feature
        mp3 = glob.glob(os.path.join(self.audio_dir, "*.mp3"))[0]
        sound = AudioSegment.from_mp3(mp3)
        sound.export(f"{self.audio_dir}/a{self.index}.wav", format="wav")
        os.remove(mp3)
        self.index += 1

    def music_meta(self, song, start=True):
        """
        Fetches meta data for a song
        NOTE: This is a tough problem to solve as the users only enter the
            song name. Currently, it fetches the first song. Needs improvement!
        """
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
        """
        Generates the entire broadcast
        This includes generating segments, synthesizing it, merging it into
        one mp3, and cleaning up the temporary files
        """
        for action, meta in self.schema:
            speech = None
            if action == "up":
                speech = self.wakeup()
                self.speak(speech, announce=True)
                speech = self.sprinkle_gpt()
                self.speak(speech)
            elif action == "music":
                for song in meta:
                    speech = self.music_meta(song)
                    self.speak(speech, announce=True)
                    self.music(song)
                    speech = self.music_meta(song, start=False)
                    self.speak(speech, announce=True)
                    speech = self.sprinkle_gpt()
                    self.speak(speech)
            elif action == "news":
                category, k = meta
                speech = self.news(category, k)
                self.speak(speech)
            elif action == "weather":
                speech = self.weather(meta)
                self.speak(speech)
            elif action == "fun":
                speech = self.on_this_day()
                self.speak(speech)
            elif action == "end":
                speech = self.over()
                self.speak(speech, announce=True)
        self.radio()
        self.cleanup()
        return 0

    def radio(self):
        """
        Merges all the audio segments into one wav file
        """
        infiles = [
            AudioSegment.from_file(f"{self.audio_dir}/a{i}.wav")
            for i in range(self.index)
        ]
        outfile = "radio.wav"
        base = infiles.pop(0)
        for infile in infiles:
            base = base.append(infile)
        base.export(outfile, format="wav")

    def cleanup(self):
        """
        Converts the main wav file to mp3 (to compress audio)
        And removes all the temporary files/dir created
        """
        src = "radio.wav"
        dest = "radio.mp3"
        # Check if dest exists and delete it
        # as FFmpeg cannot edit existing files in-place
        if Path(dest).is_file():
            os.remove(dest)
        convert = FFmpeg(
            inputs={src: None},
            outputs={dest: ["-acodec", "libmp3lame", "-b:a", "128k"]},
        )
        convert.run()

        os.remove(src)
        for index in range(self.index):
            os.remove(f"{self.audio_dir}/a{index}.wav")
        os.rmdir(f"{self.audio_dir}")

    def cleaner(self, speech):
        """
        Speech cleanup
        This is a particularly hard problem to solve
        Presently,
            abbreviation is expanded into its phones (e.g. ABC => ae bee sieh)
            some unnecessary symbols are replaced (noticed from trial and error)
            and all these is passed through Coqui-ai's cleaner
        """
        acronyms = re.findall("[A-Z](?:[\\.&]?[A-Z]){1,7}[\\.]?|[A-Z][\\.]", speech)
        for acronym in acronyms:
            cleaned_up = acronym.replace(".", "")
            pronounce = str()
            for alphabet in cleaned_up:
                pronounce += self.phones[alphabet.lower()] + " "
            speech = speech.replace(acronym, pronounce.replace(".", ""))
        return english_cleaners(
            speech.replace("..", ".").replace("’", "'").replace(".,", ",")
        )

    def speak(self, speech, announce=False):
        """
        Preprocessing before actual tts
        Text needs to be synthesized in chunks
            else the tts model has diffulties
        """
        if speech is None:
            return
        speeches = sent_tokenize(speech)
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
        """
        If speech is not an announcement, it is slowed down a bit
        This generates clear and audible segments
        """
        for index in range(start_index, self.index):
            src = f"{self.audio_dir}/a{index}.wav"
            dest = f"{self.audio_dir}/out.wav"
            slowit = FFmpeg(
                global_options=["-y"],
                inputs={src: None},
                outputs={dest: ["-filter:a", "atempo=0.85"]},
            )
            slowit.run()
            # FFmpeg cannot edit existing files in-place
            os.remove(src)
            os.rename(dest, src)

    def background_music(self):
        """
        Background music is added during announcements
        """
        background = AudioSegment.from_wav(CONF["backg_music"])
        background -= 25  # reduce the volume
        speech = AudioSegment.from_wav(f"{self.audio_dir}/a{self.index - 1}.wav")
        imposed = background.overlay(speech, position=4000)
        imposed.export(f"{self.audio_dir}/a{self.index - 1}.wav", format="wav")

    def silence(self):
        """
        Important to create distinct pauses between segments
        """
        no_audio = AudioSegment.silent(duration=2000)
        no_audio.export(f"{self.audio_dir}/a{self.index}.wav", format="wav")
        self.index += 1

    def init_speech(self):
        """
        Initializes the synthesizer for tts
        """
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
        """
        Synthesizes the text and saves it
        Speaker p267 was chosen after a thorough search through Coqui-ai's tts models
        As Coqui-ai lacks models which can generate emotions,
        the sound is a bit monotonic.
        To mitigate this, it is nice to have a deep voice.
        """
        wavs = self.synthesizer.tts(text, speaker_name="p267", style_wav="")
        self.synthesizer.save_wav(wavs, f"{self.audio_dir}/a{self.index}.wav")
        self.index += 1


if __name__ == "__main__":
    dialogue = Dialogue()
    dialogue.flow()
