import unittest
from mock import patch
from radio import Recommend

import json

from feedparser.util import FeedParserDict
from billboard import ChartEntry
from requests.models import Response


class Test_Recommend(unittest.TestCase):
    @patch("radio.parse")
    def test_news(self, mock_parse):
        mock_parse.return_value = FeedParserDict(
            {
                "entries": [
                    {
                        "title": "Title 1",
                        "summary": "Summary 1",
                    },
                    {
                        "title": "Title 2",
                        "summary": "Summary 2",
                    },
                ]
            }
        )
        rec = Recommend()
        news = rec.news("world", 2)
        self.assertEqual(mock_parse.call_count, 1)
        mock_parse.assert_called_once()
        self.assertNotEqual(news, None)
        self.assertEqual(len(news), 2)

    def test_playlist_by_genre(self):
        rec = Recommend()
        songs = rec.playlist_by_genre("rock", 2)
        self.assertNotEqual(songs, None)
        self.assertEqual(len(songs), 2)

    @patch("radio.musicbrainzngs.search_recordings")
    def test_artist_discography(self, mock_search_recordings):
        mock_search_recordings.return_value = {
            "recording-list": [
                {"title": "Song 1"},
                {"title": "Song 2"},
                {"title": "Song 3"},
            ]
        }
        rec = Recommend()
        songs = rec.artist_discography("Artist 1", 2)
        self.assertEqual(mock_search_recordings.call_count, 8)
        self.assertNotEqual(songs, None)
        self.assertEqual(len(songs), 2)

    @patch("radio.billboard.ChartData")
    def test_billboard(self, mock_ChartData):
        mock_ChartData.return_value = {
            ChartEntry("Artist 1", "Song 1", None, None, None, None, None, None),
            ChartEntry("Artist 2", "Song 2", None, None, None, None, None, None),
        }
        rec = Recommend()
        songs = rec.billboard("Chart 1", 2)
        self.assertEqual(mock_ChartData.call_count, 1)
        self.assertNotEqual(songs, None)
        self.assertEqual(len(songs), 2)

    def test_person(self):
        rec = Recommend()
        first, last, loc = rec.person()
        self.assertNotEqual(first, None)
        self.assertNotEqual(last, None)
        self.assertNotEqual(loc, None)

    def test_daily_question(self):
        rec = Recommend()
        question = rec.daily_question(question=True)
        resp = rec.daily_question(question=False)
        self.assertNotEqual(question, None)
        self.assertNotEqual(resp, None)

    def test_advertisement(self):
        rec = Recommend()
        company, advertisement = rec.advertisement()
        self.assertNotEqual(company, None)
        self.assertNotEqual(advertisement, None)

    @patch("radio.requests.get")
    def test_weather(self, mock_get):
        resp = Response()
        resp_content = {
            "current_condition": [
                {
                    "cloudcover": "100",
                    "temp_C": "5",
                    "temp_F": "41",
                    "weatherDesc": [{"value": "Overcast"}],
                    "windspeedKmph": "6",
                }
            ],
            "weather": [
                {
                    "hourly": [
                        {
                            "weatherDesc": [{"value": "Partly cloudy"}],
                        },
                    ]
                }
            ],
        }
        resp._content = json.dumps(resp_content, indent=2).encode("utf-8")
        mock_get.return_value.status_code = 201
        mock_get.return_value = resp
        rec = Recommend()
        forecast = rec.weather("City 1")
        self.assertEqual(mock_get.call_count, 1)
        self.assertNotEqual(forecast, None)
        self.assertEqual(len(forecast), 6)

    @patch("radio.requests.get")
    def test_on_this_day(self, mock_get):
        resp = Response()
        resp_content = {
            "events": [
                {"text": "event 1"},
                {"text": "event 2"},
                {"text": "event 3"},
            ]
        }
        resp._content = json.dumps(resp_content, indent=2).encode("utf-8")
        mock_get.return_value.status_code = 201
        mock_get.return_value = resp
        rec = Recommend()
        facts = rec.on_this_day(k=2)
        self.assertEqual(mock_get.call_count, 1)
        self.assertNotEqual(facts, None)
        self.assertEqual(len(facts), 2)
