# Phoenix10.1

[![Coverage Status](https://coveralls.io/repos/github/pncnmnp/phoenix10.1/badge.svg?branch=master)](https://coveralls.io/github/pncnmnp/phoenix10.1?branch=master)

![Logo of Phoenix10.1 - it is a Phoenix in the sky, disney style](https://user-images.githubusercontent.com/24948340/204136951-3a35b15a-c06c-43ca-b935-dff27651bd79.png)

Phoenix10.1 is a software to generate personalized pre-recorded internet radios that has a text-to-speech based radio jockey.

# Here's a demo to understand what it sounds like!

[![Screen Shot 2022-11-27 at 7 14 56 PM](https://user-images.githubusercontent.com/24948340/204167724-856f8d6f-c0d5-4d4a-bc36-cb9af0e13112.png)](https://soundcloud.com/parthparikh1999p/demo-of-phoenix101)

# What can it do?

This radio jockey is capable of playing your favorite songs, including tracks from your preferred artist, genre, or Billboard chart. It can automatically discover and play fascinating clips from your preferred podcasts, provide weather updates, and deliver daily news.

For a more authentic radio experience, it brightens up your day with fictional company ads, conducts daily QnA with the audience, and shares
interesting "On this day..." facts.

# Installation

It is recommended to use Python 3.10 or newer to run the code.

## Quick Start

If you're using a Debian-based distribution, you can install all dependencies using `install.sh`:
```bash
sh install.sh
```

## Manual

This software requires `ffmpeg` and `espeak`. To install them on MacOS:

```bash
brew install ffmpeg espeak
```

To install them on Linux (Debain-based):

```bash
sudo apt-get install ffmpeg espeak
```

For Windows users, to setup and use `ffmpeg`, [follow this guide from Stack Exchange](https://video.stackexchange.com/questions/20495/how-do-i-set-up-and-use-ffmpeg-in-windows). Moreover, to setup `espeak`, [use this tutorial from Stack Overflow](https://stackoverflow.com/questions/17547531/how-to-use-espeak-with-python).

To install the Python dependencies, use:

```bash
pip3 install -r ./requirements.txt
```

The software also requires installing `punkt` from `nltk`.
In a Python shell, use the following code to install `punkt`:

```python
import nltk
nltk.download("punkt")
```

To generate TTS (text-to-speech), Coqui-ai's `vits` model is used.
We recommend running a generic `TTS` command on your shell as this will prompt `TTS` to automatically install the `vits` model.

```bash
tts --text "I am excited to demo Phoenix ten point one" --model_name tts_models/en/vctk/vits --speaker_idx p267 --out_path temp.wav
```

The `vits` model requires around `150 MB` of storage.

# Creating your radio broadcast

To create your own radio, start by updating the default schema in `./data/schema.json`.

Each action in `schema.json` is a list with two indices, one mentions the action and another mentions the characteristic of that action.
Actions available are:

- `up`
  - routine to start the radio broadcast
  - characteristic value is ignored
- `music`
  - fetches and streams music
  - characteristic should contain list of song names
- `local-music`
  - streams music using locally stored songs
  - characteristic should contain either:
    - **list of paths to the audio files**
    - **list of lists** of the format `[album_path, num_of_songs]`
- `music-artist`
  - fetches and streams music (based on the artist names)
  - characteristic should contain **list of lists** of the format `[artist_name, num_of_songs]`
- `music-genre`
  - fetches and streams music (based on some specific genres)
  - characteristic should contain **list of lists** of the format `[genre, num_of_songs]`
  - [Here is a list of genres supported by Phoenix10.1](https://gist.github.com/pncnmnp/755341a694022c6b8679b1847922c62f).
- `music-billboard`
  - fetches and streams music [from Billboard charts](https://www.billboard.com/charts/)
  - characteristic should contain **list of lists** of the format `[chart_name, num_of_songs]`
- `podcast`
  - fetches an interesting clip from a podcast
  - characteristic should be a list of the format `[podcast_rss_link, max_clip_duration_in_mins]`
- `weather`
  - broadcasts the weather
  - characteristic should contain city name. Use `null` to fetch weather using your IP address.
- `news`
  - broadcasts the news using rss feeds. The rss feeds can be updated in `./data/rss.json`.
  - characteristic should be a list of the format `[category, num_of_news_items]`
- `fun`
  - broadcasts a _On this day..._ fact
  - characteristic is ignored
- `end`
  - routine to end the broadcast
  - characteristic is ignored
- `no-ads`
  - removes fictional advertisements from the broadcast. This action should come before `up`
  - characteristic value is ignored
- `no-qna`
  - removes the daily QnA from the broadcast. This action should come before `up`
  - characteristic value is ignored

# Run

Once `schema.json` is configured, run the software using:

```bash
python3 radio.py
```

Your entire broadcast would be stored in a `radio.mp3` file.

# TTS configuration

You can modify the voice of the radio jockey, the name of your radio station/host, and the volume of the background music by editing the `./config.json` file. To experiment with different voices, you can use Coqui-ai's `vits` model with the following command:

```bash
tts-server --model_name tts_models/en/vctk/vits
```

For advice on selecting the best voices, [check out this discussion](https://github.com/coqui-ai/TTS/discussions/1891#discussioncomment-3457122).

The volume of the background music can be adjusted between `0.1` and `2`. A value of `0.1` will turn off the background music, while a value of `2` doubles its volume.

# Contributing

We always welcome and greatly appreciate contributions! You can contribute in various ways, like by reporting and fixing bugs or suggesting and implementing new features. To start contributing, you can either submit a pull request or open an issue.

If you're submitting a pull request, please make sure to run [`pylint`](https://github.com/pylint-dev/pylint) before submitting. Although it's not mandatory, performing unit tests on your code is highly encouraged.

To run the unit tests, use this command (from the root directory):

```bash
python3 -m coverage run --omit */site-packages/* -m unittest
```

We also recommend using mutation testing with [`mutmut`](https://github.com/boxed/mutmut). To execute `mutmut`, run this command (once again from the root directory):

```bash
mutmut run --paths-to-mutate ./radio.py --tests-dir ./tests/ --runner 'python3 -m unittest'
```

Bear in mind that mutation testing is a costly means of evaluating your test suite and can take several hours. So, only use this while suggesting a major change.

# License

The code is open-sourced under the [MIT License](./LICENSE).

# Acknowledgements

Every software stands on the shoulders of giants, and this is no different!

- The authors would like to thank Coqui-ai and their work on TTS (licensed under [Mozilla Public License 2.0](https://github.com/coqui-ai/TTS/blob/dev/LICENSE.txt)).
- The logic to generate random identities is from [`rig`](https://launchpad.net/ubuntu/+source/rig/1.11-1build1) and the names database (`fnames.txt`, `lnames.txt`, `locdata.txt`) is from the US Census database.
- The dataset in `./data/genres.csv` is curated from the [The Million Song Dataset](http://millionsongdataset.com/).
  - The Million Song Dataset was created under a grant from the National Science Foundation, project IIS-0713334. The original data was contributed by The Echo Nest, as part of an NSF-sponsored GOALI collaboration. Subsequent donations from SecondHandSongs.com, musiXmatch.com, and last.fm, as well as further donations from The Echo Nest, are gratefully acknowledged.
- The background music is [Woke up this Morning Theme by Lobo Loco](https://freemusicarchive.org/music/Lobo_Loco/harvest-times/woke-up-this-morning-theme-fma-podcast-suggestion/) and is licensed under a [Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/).
- The questions are from [icebreakers](https://github.com/ParabolInc/icebreakers/blob/main/lib/api.ts) which is licensed under MIT License. Some of the responses were manually curated from [character.ai](https://www.character.ai/). From their [TOS](https://beta.character.ai/tos):
  - As to a user interacting with a Character created by another user or by Character AI, the user who elicits the Generations from a Character owns all rights in those Generations and grants to Character AI a nonexclusive, worldwide, royalty-free, fully paid up, transferable, sublicensable, perpetual, irrevocable license to copy, display, upload, perform, distribute, store, modify and otherwise use any Generations.
- The fictional advertisement and intros/outros were curated using the [`gpt-3.5-turbo`](https://openai.com/blog/introducing-chatgpt-and-whisper-apis) model. We followed the [Sharing & Publication Policy](https://openai.com/policies/sharing-publication-policy) of OpenAI and acknowledge that we have reviewed, edited, and revised the language of the content to our preference. We take ultimate responsibility for the content generated.
- The Logo was generated using Open AI's [Dall-E 2](https://openai.com/dall-e-2/).
