# ffmpeg-slide-gen

Combine slides and audio to produce video using ffmpeg

## What is this repo about?

This repo provides a Python script to automate the execution of `ffmpeg` in order to produce a presentation video. It takes the following as input:
- A sequence of slide images
- The audio of the presentation
- Timestamp for each of the slides

The script then computes the durations for each slide to produce a *concat* file and runs it through `ffmpeg` along with audio to generate a presentation video.

This makes it easy to record the audio of a presentation (the easiest part) and later combine it with relevant presentation with ease.

## Requirements

Tested with Python 3.9.1 but may work with other Python 3 versions. Requires a few Python libraries that can be installed (virtualenv is preferred) using the command:

```
pip install -r requirements.txt
```

Also depends on `ffmpeg` and `mediainfo` commands so make sure to have them in the shell `PATH`. Tested with the following versions:
- ffmpeg `5.1.2` (can be installed using Homebrew by running `brew install ffmpeg`)
- mediainfo `v22.12` (can be installed using Homebrew by running `brew install mediainfo`)

NOTE: All the testing was done on Mac OS Ventura `13.1`

## Usage

Run the `ffmpeg-slide-gen.py` script with `--help` to see the usage. All options are required (except `--help` itself).

```
Usage: ffmpeg-slide-gen.py [OPTIONS]

  Generate FFMpeg demux concat file from specified slides and timestamps. See:
  https://superuser.com/a/619843/26006

Options:
  -c, --slide-count TEXT          Number of slides.  [required]
  -i, --slides FILE...            List of image filenames as an ordered
                                  sequence.
  -s, --slide-timestamps, --ts <INTEGER TEXT>...
                                  Pair of: <slide-number timestamp>. Timestamp
                                  can be in seconds or min:sec. Not needed if
                                  --vlc-playlist-file is specified.
  -b, --vlc-playlist-file, --m3u FILE
                                  Specify the path to the m3u file to extract
                                  bookmarks as slide timestamps. Not needed if
                                  --slide-timestamps is specified.
  -a, --audio-file FILE           Specify the path to the audio file.
                                  [required]
  -o, --video-out TEXT            Specify the path for the output video file.
                                  [required]
  -n, --dry-run                   Enable dry-run mode, generates the concat
                                  file and prints the ffmpeg command without
                                  actually running it.
  --help                          Show this message and exit.
```

### Usage notes

- `--slides` option takes multiple image file names as arguments, but the count of the filenames must be specified using `--slide-count` option.
- `--slide-timestamps`  and `--vlc-playst-file` are mutually exclusive options as they are meant to specify the slide timestamps. Specify only one of these options.
- `--slide-timestamps` takes a pair of arguments, first being the slide number and the second being the timestamp of the slide. The timestamp can be given as seconds (`integer`), seconds.millis (`float`) or min:sec (`string`).
- `--dry-run` option runs all the logic, but instead of running  the `ffmpeg` command, it is simply echoed to the console. In dry-run mode, the temp concat file will not be deleted, so the echoed `ffmpeg` command can be executed as is.

## Overall Approach

### Approach 1

- Export presentation as images
    - A PPT file can be opened in Keynote and all slides can be exported to a folder, say /tmp/proj
    - A PDF can be exported to images using `ghostscript`, e.g., `gs -sDEVICE=jpeg -sOutputFile=page-%03d.jpg -r1280x720 -f file.pdf`
- Generate an interim video by running `ffmpeg-slide-gen.py` with just the first slide
- Open the presentation and the intermim video
- While playing the video, [add a bookmark](https://superuser.com/a/1765955/26006) at each location when a slide starts and rename it with the slide number
- At the end [save it as a playlist](https://superuser.com/a/1765955/26006) which should create a `.m3u` file
- Rerun `ffmpeg-slide-gen.py` with the `m3u` file as input to produce the final video.

#### Sample commands

```shell
$ python ffmpeg-slide-gen.py -a /tmp/proj/audio.mp4 -o /tmp/proj/video-tmp.mp4 -c $(echo /tmp/proj/*.jpeg | wc -w) -i /tmp/proj/*.jpeg -s 1 0
$ cat /tmp/video.m3u
#EXTM3U
#EXTINF:2438,video-tmp.mp4
#EXTVLCOPT:bookmarks={name=1,time=0},{name=2,time=5},{name=3,time=35},{name=4,time=40},{name=5,time=105},{name=6,time=476},{name=7,time=719},{name=8,time=832},{name=9,time=892},{name=10,time=904},{name=11,time=965},{name=12,time=979},{name=13,time=1068},{name=14,time=1167},{name=15,time=1178},{name=14,time=1261},{name=16,time=1310},{name=15,time=1406},{name=17,time=2139}
file:///private/tmp/video-tmp.mp4
$ python ffmpeg-slide-gen.py -a /tmp/proj/audio.mp4 -o /tmp/proj/video.mp4 -c $(echo /tmp/proj/*.jpeg | wc -w) -i /tmp/proj/*.jpeg -b /tmp/video.m3u

```

### Approach 2

- Export presentation as images
    - A PPT file can be opened in Keynote and all slides can be exported to a folder, say /tmp/proj
    - A PDF can be exported to images using `ghostscript`, e.g., `gs -sDEVICE=jpeg -sOutputFile=page-%03d.jpg -r1280x720 -f file.pdf`
- Open the presentation and play the audio to identify the timestamps
- Whenever a change in slide is observed, take a note of the slide number and timestamp (in seconds)
- Use the above timestamps to construct the command-line to produce final video

#### Sample command

```shell
$ python ffmpeg-slide-gen.py -a /tmp/proj/audio.mp4 -o /tmp/proj/video.mp4 -c $(echo /tmp/proj/*.jpeg | wc -w) -i /tmp/proj/*.jpeg \
  -s 1 0 \
  -s 2 5 \
  -s 3 35 \
  -s 4 40 \
  -s 5 105 \
  -s 6 476 \
  -s 7 719 \
  -s 8 832 \
  -s 9 892 \
  -s 10 904 \
  -s 11 965 \
  -s 12 979 \
  -s 13 1068 \
  -s 14 1167 \
  -s 15 1178 \
  -s 14 1261 \
  -s 16 1310 \
  -s 15 1406 \
  -s 17 2139
```

As can be seen above, slide numbers can be repeated and in any order, in case the presenter doesn't go through them sequentially or goes back and forth.

### Addendum

This repo also comes with the `youtube-transcript.py` script that can be used to retrieve autogenerated transcript from a YouTube video. It is most useful to do the following:
- Uload the interim video file generated in *Approach 1* to your YouTube account as an unlisted video.
- Wait for a few hours for YouTube to generate the transcript for the audio from the presentation.
- Run the tool to dump the transcript to an HTML file, e.g., `python youtube-transcript.py -d 0 -s abcdefghijk`
- Open the HTML file in a browser and use that as a reference to locate the timestamps for slides, e.g., you can look for certain keywords like "slide" (when the presenter speaks of slide numbers) or slide titles and unique keywords in the slide
  content.

#### Usage

```
Usage: youtube-transcript.py [OPTIONS] VIDEO_ID

Options:
  -d, --interval-duration, --id INTEGER
                                  Interval duration for generating timestamps,
                                  use 0 to disable and produce raw output
  -s, --timestamp-in-seconds, --tis
                                  Specify to see duration in seconds instead
                                  of min:sec
  --help                          Show this message and exit.
```

**NOTE**: the above sample commands rely on the shell wildcard expansion to order them sequentially, which works as expected for the slides exported from Keynote on a Mac computer.
