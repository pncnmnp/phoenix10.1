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
import logging
import random
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
import uuid

import billboard
import eyed3
from eyed3.id3.frames import ImageFrame
from feedparser import parse
from ffmpy import FFmpeg
import itunespy
import matplotlib
import musicbrainzngs
import nltk
from nltk import sent_tokenize
import numpy
import pandas as pd
import podcastparser
from pydub import AudioSegment
import randimage
import requests
import ytmdl
import yt_dlp

from TTS.server.server import create_argparser
from TTS.tts.utils.text.cleaners import english_cleaners
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer
from TTS import __file__ as tts_path

with open("./config.json", "r", encoding="UTF-8") as conf_file:
    _CONFIG = json.load(conf_file)
    PATH = _CONFIG["PATH"]
    TTS = _CONFIG["TTS"]

_logger = logging.getLogger()
_logger.setLevel(logging.INFO)
logging.getLogger('musicbrainzngs').setLevel(logging.WARNING)

class _SuppressTTSLogs:
    """
    Suppresses print statements from Coqui-ai's TTS
    From: https://stackoverflow.com/a/45669280/7543474
    Licensed under CC BY-SA 4.0
    """

    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout


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

    def title(self):
        """
        Recommends a title for the radio show
        GPT-3.5-turbo was used to generate the titles
        The prompt used was:
            What can be the title of an AI generated radio station?
            Suggest something that is very short (like two words) and catchy
            Give me titles in form of a Python list.
            I want 7 titles that include the days of the week
            (like Monday Melodies), and 4 titles which contain
            parts of the day (morning/evening/afternoon/late-night).
            So 11 in total.
        """
        days = [
            "Monday Mixtape",
            "Tune-Up Tuesday",
            "Wavelength Wednesday",
            "Throwback Thursday",
            "Funky Friday Fiesta",
            "Saturdaze Sensations",
            "Sunday Soundwaves",
        ]
        timeofday = [
            "Late-Night Live",
            "Morning Mix",
            "Afternoon Acoustics",
            "Evening Euphoria",
        ]
        if random.random() < 0.5:
            day = datetime.datetime.today().weekday()
            return days[day]
        when = (datetime.datetime.today().hour) // 6
        return timeofday[when]

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

    def local_music(self, path, num_songs):
        """
        Recommends music from the local music directory
        """
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            songs = glob.glob(path + "/*.mp3")
            random.shuffle(songs)
            return songs[: int(num_songs)]
        elif os.path.isfile(path) and num_songs == 1:
            return [path]
        else:
            return []

    def music_intro_outro(self):
        """
        Recommends a music intro/outro
        GPT-3.5-turbo was used to generate the responses
        The prompt used was:
        For intros,
            how do radio hosts introduce a song?
            Can you give me some interesting phrases?
            Put them in a JSON list
            Recommend some normal intros, not too hyped up.
            We do not know what kind of song to recommend,
            so do not assume a genre or a mood.
            Something generic and neutral and fun.
        For outros,
            something that can be said after the song is finished?
            again, We do not know what kind of song to recommend,
            so do not assume a genre or a mood.
            Something generic and neutral and fun.
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
        GPT-3.5-turbo was used to generate the responses
        GPT-3.5-turbo phrase used was -
            Can you make advertisements about these companies?
            <Fictional company names>

            Keep it short and fun - like less than 300 characters.
            Each ad should start with the following:
                Today's broadcast is sponsered by <COMPANY_NAME>.
                <COMPANY_NAME> is a <WHAT IT DOES> that <REST OF THE AD>.
            Do it in a JSON format - key is the name of the company
            and value is what the jockey will say.

            Say as it the radio jockey is talking to the audience,
            so use pronouns like they to describe the company.
            Also, instead of Company 1, Company 2 in the keys,
            put the actual company name in it.
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
        facts = sorted(events, key=len)[:k]
        return facts


class Dialogue:
    """
    Generates and synthesizes speech for the radio personality
    Also, fetches music and its metadata
    """

    def __init__(self, audio_dir=None):
        self.rec = Recommend()
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
            f"You are tuning into {self.cleaner(TTS['station_name'])}! "
            f"I am your host {TTS['host_name']}. "
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
            logging.info(f"Generating fictional advertisement for {company}.")
            end = f" Thank you {company} for sponsoring today's broadcast. "
            return speech + end
        if self.rec.question is None:
            logging.info("Generating daily question.")
            ques = self.rec.daily_question()
            speech = (
                "And now it is time for today's daily question. "
                f"Are you Ready? Alright! Today's question is - {ques} "
                f"You can post your answers on Twitter, hashtag {self.cleaner(TTS['station_name'])}, "
                "and we will read it on our broadcast. "
            )
            return speech
        if self.rec.question:
            logging.info("Generating daily question response.")
            ans = self.rec.daily_question(question=False)
            fname, lname, loc = self.rec.person()
            speech = (
                "Wow! Seems like your answers to our daily question are rolling in. "
                f"My favorite is from {fname} {lname} from {loc}. "
                f"They say that - {ans}"
                f" A great response! Thank you {fname}! "
            )
            return speech
        return str()

    def over(self):
        """
        Routine to end the broadcast
        """
        speech = (
            "And that's it for today's broadcast! "
            f"Thanks for listening to {self.cleaner(TTS['station_name'])}! "
            "Hope you have a great day ahead! See You! "
        )
        return speech

    def news(self, category, k):
        """
        Speech to convey the daily news for a specific category
        """
        logging.info(f"Fetching {k} news items for {category}.")
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
        logging.info(f"Fetching weather forecast for {location}.")
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

    def music(self, song, artist):
        """
        Fetches a song
        """
        args = ytmdl.main.arguments()
        args.SONG_NAME = [song]
        if artist:
            args.artist = artist
        args.choice = 1
        args.quiet = True
        url, _ = ytmdl.core.search(args.SONG_NAME[0], args)
        logging.info(f"Fetching song from {url}.")

        # Download the song with metadata
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                },
                {"key": "FFmpegMetadata"},
            ],
            "outtmpl": f"{self.audio_dir}/%(title)s.%(ext)s",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([url])
            if error_code != 0:
                return 1
        mp3 = glob.glob(f"{self.audio_dir}/*.mp3")[0]
        os.rename(mp3, f"{self.audio_dir}/song.mp3")
        return 0

    def postprocess_music(self, song, is_local):
        """
        Generate the wav file for music and sandwich it between the intro and outro
        """
        song_path = song if is_local else f"{self.audio_dir}/song.mp3"
        sound = AudioSegment.from_mp3(song_path)

        # Rename the previous outro file to current index
        # as the previous outro index will be used for this song
        # This ensures that the song is sandwiched between intro and outro
        # NOTE: index - 1 is a silence clip
        os.rename(
            f"{self.audio_dir}/a{self.index - 2}.wav",
            f"{self.audio_dir}/a{self.index}.wav",
        )
        sound.export(f"{self.audio_dir}/a{self.index - 2}.wav", format="wav")
        self.index += 1
        if not is_local:
            os.remove(song_path)

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
                "Recently, I have been listening to"
                f"{parsed['title']} from {parsed['itunes_author']}. "
                "Please sit back, relax, and enjoy this short clip from them. "
            )
        else:
            speech = (
                "Wow! That was something, wasn't it? "
                "The podcast you just listened to was "
                f"{parsed['title']} from {parsed['itunes_author']}. "
                "If you enjoyed it, please do check them out."
            )
        return speech

    def podcast_clip(self, rss_feed, duration):
        """
        Fetches an interesting clip from the podcast
        """
        # Download the podcast
        parsed = podcastparser.parse(rss_feed, urllib.request.urlopen(rss_feed))
        logging.info(
            f"Finding a relevant clip from podcast - {parsed['title']} from {parsed['itunes_author']}."
        )
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
            ],
            check=False,
        )

        # Find out sections of podcast which have a long pause
        # This will help us split the podcast into pieces
        # Logic is from mxl: https://stackoverflow.com/a/57126101
        # Licensed under CC BY-SA 4.0
        # Pydub is way slow for this task
        silence_timestamps = []
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
                "-hide_banner", 
                "-loglevel", 
                "error",
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
            logging.warning(
                f"No relevant podcast clip found. Using the first {duration} minutes."
            )
            optimal_start, optimal_end = None, None
            optimal_clip = AudioSegment.from_mp3(audio_file)[: duration_sec * 1000]

        optimal_clip.export(audio_file.replace(".mp3", ".wav"), format="wav")
        os.remove(audio_file)
        self.index += 1
        self.silence()

    def music_meta(self, song, artist, is_local, start=True):
        """
        Fetches metadata for a song
        NOTE: This is a tough problem to solve for non-local songs
        as the users only enter the song name.
        Currently, it fetches the first song. Needs improvement!
        """
        if is_local:
            metadata = eyed3.load(song)
            artist, song = metadata.tag.artist, metadata.tag.title
            genre = "The next song is from your personal collection. "
        else:
            fetched_artist = eyed3.load(f"{self.audio_dir}/song.mp3").tag.artist

            # Compare the artist name fetched from song
            # with artists found from iTunes and choose the most similar one
            try:
                itunes_metadata = itunespy.search_track(song, country="US", limit=100)
            except:
                logging.warning(
                    "Metadata search failed. Trying again after 80 seconds."
                )
                time.sleep(80)
                itunes_metadata = itunespy.search_track(song, country="US", limit=100)
            most_accurate = sorted(
                [song_info.json for song_info in itunes_metadata],
                key=lambda song_info: nltk.edit_distance(
                    song_info["artistName"], fetched_artist
                ),
            )[0]
            artist = artist if artist else most_accurate["artistName"]
            song = song if song else most_accurate["trackName"]
            genre = f'The next song is from the world of {most_accurate["primaryGenreName"]}. '
        intro, outro = self.rec.music_intro_outro()
        song_details = f"{song} by {artist}. " if (song and artist) else ""
        if start:
            speech = f"{intro} " f"{genre}" f"{song_details}"
            return speech
        speech = (
            f"{outro} "
            f"{'The track was ' if song_details != '' else ''}{song_details}"
            f"You are listening to {self.cleaner(TTS['station_name'])}! "
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
                discography += songs
        elif action == "music-billboard":
            for chart, num_songs in meta:
                songs = self.rec.billboard(chart, num_songs)
                discography += songs
        elif action == "local-music":
            for loc_song in meta:
                songs = (
                    self.rec.local_music(*loc_song)
                    if isinstance(loc_song, list)
                    else self.rec.local_music(loc_song, 1)
                )
                discography += [(None, song) for song in songs]
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
        logging.info("Creating a broadcast.")
        self.synthesizer = self.init_speech()
        for action, meta in self.schema:
            logging.info(f"Generating {action} segment.")
            speech = None
            if action == "no-ads":
                self.rec.ad_prob = 0
                logging.info("Disabled ads.")
            elif action == "no-qna":
                self.rec.question = False
                logging.info("Disabled QnA.")
            elif action == "up":
                speech = self.wakeup()
                self.speak(speech, announce=True)
                speech = self.sprinkle_gpt()
                self.speak(speech)
            elif action.startswith("music") or action.startswith("local-music"):
                is_local = action.startswith("local-music")
                songs = self.curate_discography(action, meta)
                for artist, song in songs:
                    if not is_local:
                        error = self.music(song, artist)
                        if error:
                            logging.warning(f"Failed to download {song}. Skipping.")
                            continue
                    speech = self.music_meta(song, artist, is_local)
                    self.speak(speech, announce=True)
                    speech = self.music_meta(song, artist, is_local, False)
                    self.speak(speech, announce=True)
                    self.postprocess_music(song, is_local)
                    speech = self.sprinkle_gpt()
                    self.speak(speech)
            elif action == "podcast":
                rss_feed, duration = meta
                if duration is None:
                    logging.warning("Duration not specified. Setting it to 15 mins.")
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
        logging.info("Broadcast created.")
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
            global_options=["-hide_banner", "-loglevel", "error"],
            inputs={src: None},
            outputs={dest: ["-acodec", "libmp3lame", "-b:a", "128k"]},
        )
        convert.run()
        self.metadata(f"./{dest}")

        os.remove(src)
        for index in range(self.index):
            os.remove(f"{self.audio_dir}/a{index}.wav")
        os.rmdir(f"{self.audio_dir}")

    def metadata(self, dest):
        """
        Add metadata for the dest file
        """
        today = datetime.date.today().strftime("%d %b %y")
        title = self.rec.title() + ": " + today
        album = f"{TTS['station_name']}'s broadcast"
        artist = TTS["station_name"]
        audiofile = eyed3.load(dest)
        # Add poster
        poster_path = f"{self.audio_dir}/poster.jpeg"
        poster = randimage.utils.get_random_image((512, 512))
        matplotlib.image.imsave(poster_path, poster)
        with open(poster_path, "rb") as image_file:
            audiofile.tag.images.set(
                ImageFrame.FRONT_COVER, image_file.read(), "image/jpeg"
            )
        # Add metadata
        audiofile.tag.title = title
        audiofile.tag.album = album
        audiofile.tag.artist = artist
        audiofile.tag.save()
        # Cleanup
        os.remove(poster_path)

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
        for _speech in speeches:
            curr = say + _speech
            if len(curr) > 200:
                self.save_speech(self.cleaner(say))
                say = str()
            say += _speech + " "
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
                global_options=["-y", "-hide_banner", "-loglevel", "error"],
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
        logging.info("Adding background music in this announcement.")
        background = AudioSegment.from_wav(PATH["backg_music"])
        background -= 25 * (1 / TTS["backg_music_vol"])  # reduce the volume
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
        with _SuppressTTSLogs():
            args = create_argparser().parse_args()
            args.model_name = "tts_models/en/vctk/vits"
            path = Path(tts_path).parent / "./.models.json"
            manager = ModelManager(path)
            model_path, config_path, model_item = manager.download_model(
                args.model_name
            )
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
        if text.strip() != "":
            logging.info(f"Synthesizing speech for - {text}")
        if not hasattr(self, "synthesizer"):
            with _SuppressTTSLogs():
                self.synthesizer = self.init_speech()
        if text:
            with _SuppressTTSLogs():
                wavs = self.synthesizer.tts(
                    text, speaker_name=TTS["speaker_name"], style_wav=""
                )
            self.synthesizer.save_wav(wavs, f"{self.audio_dir}/a{self.index}.wav")
            self.index += 1


if __name__ == "__main__":
    dialogue = Dialogue()
    dialogue.flow()
