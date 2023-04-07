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
import subprocess
import urllib.request
import uuid

import billboard
from feedparser import parse
from ffmpy import FFmpeg
import musicbrainzngs
from nltk import sent_tokenize
import numpy
import pandas as pd
import podcastparser
from pydub import AudioSegment
import requests
import ytmdl

from TTS.server.server import create_argparser
from TTS.tts.utils.text.cleaners import english_cleaners
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer
from TTS import __file__ as tts_path

with open("./config.json", "r", encoding="UTF-8") as conf_file:
    PATH = json.load(conf_file)["PATH"]


class Recommend:
    """
    Recommends content for the radio personality
    """

    def __init__(self):
        self.ad_prob = 1
        self.question = None
        with open(PATH["rss"], "r", encoding="UTF-8") as file:
            self.rss_urls = json.load(file)
        musicbrainzngs.set_useragent(
            "phoenix10.1", "1", "https://github.com/pncnmnp/phoenix10.1"
        )

    def news(self, category="world", k=5):
        """
        Recommends news based on the news category
        """
        paper = parse(self.rss_urls[category])
        info = []
        for source in paper.entries[:k]:
            info += [source["title"] + ". " + source["summary"]]
        return info

    def playlist_by_genre(self, genre, num_songs=3):
        """
        Recommends music given a genre
        List of genres supported:
            https://gist.github.com/pncnmnp/755341a694022c6b8679b1847922c62f
        """
        songs = pd.read_csv(PATH["songdata"], compression="gzip")
        by_genre = songs[songs.apply(lambda song: genre in song["tags"], axis=1)]
        relevant_songs = list(
            by_genre[["artist_name", "title"]].itertuples(index=False, name=None)
        )
        random.shuffle(relevant_songs)
        return relevant_songs[: int(num_songs)]

    def artist_discography(self, artist_name, num_songs=10):
        """
        Recommends music given an artist name
        """
        titles = set()
        for offset in range(0, 200, 25):
            discography = musicbrainzngs.search_recordings(
                artistname=artist_name, offset=offset
            )
            for record in discography["recording-list"]:
                titles.add(record["title"])
        titles = list(titles)
        random.shuffle(titles)
        return titles[: int(num_songs)]

    def billboard(self, chart, num_songs=3):
        """
        Recommends music given a Billboard chart
        """
        chart_data = billboard.ChartData(chart)
        songs = [(song.artist, song.title) for song in chart_data]
        random.shuffle(songs)
        return songs[: int(num_songs)]

    def music_intro_outro(self):
        """
        Recommends a music intro
        """
        with open(PATH["music_intro_outro"], "r", encoding="UTF-8") as file:
            phrases = json.load(file)
        return random.choice(phrases["intros"]), random.choice(phrases["outros"])

    def person(self):
        """
        Provides a random identity -
            first name, last name, and place of residence
        Uses data from Linux's rig utility
        """
        with open(PATH["fname"], "r", encoding="UTF-8") as file:
            first = random.choice(file.readlines()).strip()
        with open(PATH["lname"], "r", encoding="UTF-8") as file:
            last = random.choice(file.readlines()).strip()
        with open(PATH["locdata"], "r", encoding="UTF-8") as file:
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
            with open(PATH["daily_ques"], "r", encoding="UTF-8") as file:
                questions = json.load(file)
                self.question = random.choice(list(questions.keys()))
                return self.question
        else:
            with open(PATH["daily_ques"], "r", encoding="UTF-8") as file:
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
            with open(PATH["ads"], "r", encoding="UTF-8") as file:
                ads = json.load(file)
            self.ad_prob /= 4
            company = random.choice(list(ads.keys()))
            return company, ads[company]
        return None, None

    def weather(self, location):
        """
        Fetches weather forecast
        """
        if location is not None:
            req = requests.get(f"https://wttr.in/{location}?format=j1", timeout=100)
        else:
            req = requests.get("https://wttr.in?format=j1", timeout=100)
        forecast = req.json()["current_condition"][0]
        next_hour = req.json()["weather"][0]["hourly"][0]["weatherDesc"][0]["value"]
        summary = {
            "weather": forecast["weatherDesc"][0]["value"],
            "c": forecast["temp_C"],
            "f": forecast["temp_F"],
            "next_hour": next_hour,
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

    def __init__(self, audio_dir=None):
        self.rec = Recommend()
        self.synthesizer = self.init_speech()
        with open(PATH["schema"], "r", encoding="UTF-8") as file:
            self.schema = json.load(file)
        with open(PATH["phones"], "r", encoding="UTF-8") as file:
            self.phones = json.load(file)
        self.index = 0
        # Used to store intermediate audio clips
        if audio_dir is None:
            self.audio_dir = "./" + uuid.uuid4().hex[:10]
            os.makedirs(self.audio_dir)
        else:
            self.audio_dir = audio_dir
            os.makedirs(self.audio_dir, exist_ok=True)

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
        company, speech = self.rec.advertisement()
        if speech is not None:
            end = f" Thank you {company} for sponsoring today's broadcast. "
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
        loc = location if location is not None else "your region"
        speech = (
            f'It seems like the weather today in {loc} is going to be {forecast["weather"]}. '
            f'Presently, it is {forecast["c"]} degree celcius '
            f'and {forecast["f"]} degree fahrenheit. '
            f'The next hour is going to be {forecast["next_hour"]}. '
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

    def music(self, song, artist=None):
        """
        Fetches a song
        """
        args = ytmdl.main.arguments()
        args.SONG_NAME = [song]
        if artist:
            args.artist = artist
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

    def podcast_dialogue(self, rss_feed, start=True):
        """
        Speech for a podcast
        """
        parsed = podcastparser.parse(rss_feed, urllib.request.urlopen(rss_feed))
        if start:
            speech = (
                "You know, I love listening to podcasts. "
                "The beautiful thing about it is that podcasting is just talking. "
                "It can be funny, or it can be terrifying. "
                "It can be sweet. It can be obnoxious. "
                "It almost has no definitive form. "
                "In that sense it is one of the best ways to explore an idea. "
                f"Recently, I have been listening to {parsed['title']} from {parsed['itunes_author']}. "
                "Please sit back, relax, and enjoy this short clip from them. "
            )
        else:
            speech = (
                "Wow! That was something, wasn't it? "
                f"The podcast you just listened to was {parsed['title']} from {parsed['itunes_author']}. "
                "If you enjoyed it, please do check them out."
            )
        return speech

    def podcast_clip(self, rss_feed, duration):
        """
        Fetches an interesting clip from the podcast
        """
        # Download the podcast
        parsed = podcastparser.parse(rss_feed, urllib.request.urlopen(rss_feed))
        podcast_link = parsed["episodes"][0]["enclosures"][0]["url"]
        audio_file = f"{self.audio_dir}/a{self.index}.mp3"
        subprocess.run(
            [
                "yt-dlp",
                "--extract-audio",
                "--audio-format",
                "mp3",
                "--max-downloads",
                "1",
                f"{podcast_link}",
                "--output",
                f"{audio_file}",
            ]
        )

        # Find out sections of podcast which have a long pause
        # This will help us split the podcast into pieces
        # Logic is from mxl: https://stackoverflow.com/a/57126101
        # Licensed under CC BY-SA 4.0
        # Pydub is way slow for this task
        silence_timestamps = list()
        duration_sec = duration * 60
        silence_duration = 1.1
        threshold = int(float(0.1 * 65535))
        sampling_rate = 22050
        threshold_sampling_rate = silence_duration * sampling_rate
        buffer_length = int(threshold_sampling_rate * 2)

        # dummy array for the first chunk
        prev_arr = numpy.arange(1, dtype="int16")
        position, prev_position = 0, 0
        pipe = subprocess.Popen(
            [
                "ffmpeg",
                "-i",
                f"{audio_file}",
                "-f",
                "s16le",  # PCM signed 16-bit little-endian
                "-acodec",
                "pcm_s16le",
                "-ar",
                str(sampling_rate),
                "-ac",
                "1",  # for mono
                "-",  # - output to stdout
            ],
            stdout=subprocess.PIPE,
            bufsize=10**8,
        )

        while True:
            raw = pipe.stdout.read(buffer_length)
            if len(prev_arr) == 0 or raw == "":
                break
            curr_arr = numpy.fromstring(raw, dtype="int16")
            curr_range = numpy.concatenate([prev_arr, curr_arr])
            maximum = numpy.amax(curr_range)
            if maximum <= threshold:
                # pass filter with all samples <= threshold set to 0
                # and > threshold set to 1
                trng = (curr_range <= threshold) * 1
                samples = numpy.sum(trng)
                # check how many 1's were there
                if samples >= threshold_sampling_rate:
                    end_time = position + silence_duration * 0.5
                    time = (end_time) - prev_position
                    if time <= duration_sec:
                        silence_timestamps.append((prev_position, end_time))
                    prev_position = position + silence_duration * 0.5
            position += silence_duration
            prev_arr = curr_arr

        silence_timestamps = sorted(
            silence_timestamps, key=lambda time: time[1] - time[0], reverse=True
        )
        try:
            optimal_start, optimal_end = silence_timestamps[0]
            podcast_audio = AudioSegment.from_mp3(audio_file)
            optimal_clip = podcast_audio[optimal_start * 1000 : optimal_end * 1000]
        except IndexError:
            # If no silence is found, just take the first "duration" minutes
            optimal_start, optimal_end = None, None
            optimal_clip = AudioSegment.from_mp3(audio_file)[: duration_sec * 1000]

        optimal_clip.export(audio_file.replace(".mp3", ".wav"), format="wav")
        os.remove(audio_file)
        self.index += 1
        self.silence()

    def music_meta(self, song, artist=None, start=True):
        """
        Fetches meta data for a song
        NOTE: This is a tough problem to solve as the users only enter the
            song name. Currently, it fetches the first song. Needs improvement!
        """
        try:
            info = ytmdl.metadata.get_from_itunes(song)[0].json
        except TypeError:
            return None
        info["artistName"] = artist if artist else info["artistName"]
        intro, outro = self.rec.music_intro_outro()
        if start:
            speech = (
                f"{intro} "
                f'The next song is from the world of {info["primaryGenreName"]}. '
                f'{info["trackName"]} by {info["artistName"]}. '
            )
            return speech
        else:
            speech = (
                f"{outro} "
                f'The track was {info["trackName"]} by {info["artistName"]}. '
                "You are listening to Phoenix ten point one! "
            )
            return speech

    def curate_discography(self, action, meta):
        """
        Generates a discography where each element is (artist name, song)
        """
        discography = []
        if action == "music-artist":
            for artist, num_songs in meta:
                songs = self.rec.artist_discography(artist, num_songs)
                discography += [(artist, song) for song in songs]
        elif action == "music-genre":
            for genre, num_songs in meta:
                songs = self.rec.playlist_by_genre(genre, num_songs)
                discography += [(artist, song) for artist, song in songs]
        elif action == "music-billboard":
            for chart, num_songs in meta:
                songs = self.rec.billboard(chart, num_songs)
                discography += songs
        else:
            for artist_song in meta:
                artist, song = (
                    artist_song
                    if isinstance(artist_song, list)
                    else (None, artist_song)
                )
                discography += [(artist, song)]
        if action[:6] == "music-":
            random.shuffle(discography)
        return discography

    def flow(self):
        """
        Generates the entire broadcast
        This includes generating segments, synthesizing it, merging it into
        one mp3, and cleaning up the temporary files
        """
        for action, meta in self.schema:
            speech = None
            if action == "no-ads":
                self.rec.ad_prob = 0
            elif action == "up":
                speech = self.wakeup()
                self.speak(speech, announce=True)
                speech = self.sprinkle_gpt()
                self.speak(speech)
            elif action[:5] == "music":
                songs = self.curate_discography(action, meta)
                for artist, song in songs:
                    speech = self.music_meta(song, artist)
                    if speech is None:
                        # At this point, it is likely that the
                        # song name is garbage. It is best to skip this song,
                        # than to show the user some random song
                        continue
                    self.speak(speech, announce=True)
                    self.music(song, artist)
                    speech = self.music_meta(song, artist, False)
                    self.speak(speech, announce=True)
                    speech = self.sprinkle_gpt()
                    self.speak(speech)
            elif action == "podcast":
                rss_feed, duration = meta
                if duration == None:
                    duration = 15
                speech = self.podcast_dialogue(rss_feed)
                self.speak(speech, announce=True)
                self.podcast_clip(rss_feed, int(duration))
                speech = self.podcast_dialogue(rss_feed, start=False)
                self.speak(speech, announce=True)
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
            speech.replace("..", ".")
            .replace("’", "'")
            .replace(".,", ",")
            .replace("?.", "?")
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
        background = AudioSegment.from_wav(PATH["backg_music"])
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
