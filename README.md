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

Also depends on `ffmpeg` and `mediainfo` commands so make sure to have them in the shell `PATH`.

## Usage

Run the `ffmpeg-slide-gen.py` script with `--help` to see the usage. All options are required (except `--help` itself).

```
Usage: ffmpeg-slide-gen.py [OPTIONS]

  Generate FFMpeg demux concat file from specified slides and timestamps. See:
  https://superuser.com/a/619843/26006

Options:
  -c, --slide-count TEXT          Number of slides  [required]
  -i, --slides FILE...            List of image filenames as an ordered
                                  sequence  [required]
  -s, --slide-ts, --ts <INTEGER INTEGER>...
                                  Pair of integers: slide timestamp
                                  [required]
  -a, --audio-file FILE           Specify the path to the audio file
                                  [required]
  -o, --video-out TEXT            Specify the path for the output video file
                                  [required]
  --help                          Show this message and exit.
```

## Overall Approach

- Export presentation as images
    - A PPT file can be opened in Keynote and all slides can be exported to a folder, say /tmp/proj
    - A PDF can be exported to images using `ghostscript`, e.g., `gs -sDEVICE=jpeg -sOutputFile=page-%03d.jpg -r1280x720 -f file.pdf`
- Open the presentation and play the audio to identify the timestamps.
- Whenever a change in slide is observed, take a note of the slide number and timestamp (in seconds)
- Use the above timestamps to construct the command-line to produce final video

## Sample command-line

```
python ffmpeg-slide-gen.py -a /tmp/proj/audio.mp4 -o /tmp/proj/video.mp4 -c $(echo /tmp/proj/*.jpeg | wc -w) -i /tmp/proj/*.jpeg \
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

NOTE: the above command relies on the shell wildcard expansion to order them sequentially, which works as expected for the slides exported from Keynote on a Mac computer.

As can be seen above, slide numbers can be repeated and in any order, in case the presenter doesn't go through them sequentially or goes back and forth.
