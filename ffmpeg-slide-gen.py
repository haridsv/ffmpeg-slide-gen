import sys
import re
from functools import partial
from operator import itemgetter
from typing import Tuple
from tempfile import NamedTemporaryFile

import click
import sh


def with_dynamic_narg(cnt_opt, tgt_opt):
    class DynamicNArgSetter(click.Command):
        def parse_args(self, ctx, args):
            ctx.resilient_parsing = True
            parser = self.make_parser(ctx)
            opts, _, _ = parser.parse_args(args=list(args))
            if cnt_opt in opts:
                for p in self.params:
                    if isinstance(p, click.Option) and p.name == tgt_opt:
                        p.nargs = int(opts[cnt_opt])

            ctx.resilient_parsing = False
            return super().parse_args(ctx, args)

    return DynamicNArgSetter


@click.command(cls=with_dynamic_narg('slide_count', 'slides'))
#@click.option("--total-duration", "--td", "-t", type=click.INT, required=True, help="Total duration of the video in seconds")
@click.option("--slide-count", "-c", required=True, help="Number of slides.")
@click.option("--slides", "-i", nargs=0, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="List of image filenames as an ordered sequence.")
@click.option("--slide-timestamps", "--ts", "-s", "slide_timestamps", multiple=True, type=(int, str), help="Pair of: <slide-number timestamp>. Timestamp can be in seconds or min:sec. Not needed if --vlc-playlist-file is specified.")
@click.option("--vlc-playlist-file", "--m3u", "-b", type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Specify the path to the m3u file to extract bookmarks as slide timestamps. Not needed if --slide-timestamps is specified.")
@click.option("--audio-file", "-a", required=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Specify the path to the audio file.")
@click.option("--video-out", "-o", required=True, help="Specify the path for the output video file.")
@click.option("--video-scale", "-vs", default="1280:720", show_default=True, help="Specify an alternative scale for output video")
@click.option("--dry-run", "-n", is_flag=True, default=False, help="Enable dry-run mode, generates the concat file and prints the ffmpeg command without actually running it.")
def main(slide_count, slides, slide_timestamps, vlc_playlist_file, audio_file, video_out, video_scale, dry_run):
    """
    Generate FFMpeg demux concat file from specified slides and timestamps.
    See: https://superuser.com/a/619843/26006
    """
    if slide_timestamps and vlc_playlist_file:
        raise click.UsageError("--slide-timestamps and --vlc-playlist-file are mutually exclusive options")
    elif not (slide_timestamps or vlc_playlist_file):
        raise click.UsageError("One of the --slide-timestamps and --vlc-playlist-file options must be specified")

    if vlc_playlist_file:
        bookmark_line_pat = re.compile(r"^#EXTVLCOPT:bookmarks=\{.*\}$")
        bookmark_pat = re.compile(r"\{name=([^,]+),time=([^}]+)\}")
        bookmarks = []
        with open(vlc_playlist_file, "r") as m3u_file:
            for line in m3u_file:
                line_match = bookmark_line_pat.match(line)
                if line_match:
                    for slide_no, slide_ts in bookmark_pat.findall(line):
                        if not slide_no.isdigit():
                            raise click.UsageError(f"Bookmark name: {slide_no} is invalid as a slide number, only integers are accepted")
                        slide_no = int(slide_no)
                        try:
                            slide_ts = slide_ts.isdigit() and int(slide_ts) or float(slide_ts)
                        except ValueError:
                            raise click.UsageError(f"Bookmark timestamp: {slide_ts} is invalid, only integers and floats are accepted")
                        bookmarks.append((slide_no, slide_ts))
        slide_timestamps = bookmarks
    else:
        slide_timestamps = [(slide_no, to_timestamp(slide_ts)) for slide_no, slide_ts in slide_timestamps]

    slide_idx = dict(enumerate(isinstance(slides, Tuple) and slides or [slides], start=1))
    total_duration = int(sh.mediainfo('--Inform=Audio;%Duration%', audio_file)) / 1000
    click.echo(f"Total duration of the video will be: {total_duration} seconds")

    slide_durs = []
    last_no = 1
    last_ts = 0
    for entry_no, (slide_no, slide_ts) in enumerate(sorted(slide_timestamps, key=itemgetter(1)), start=1):
        if slide_no not in slide_idx:
            raise click.UsageError(f"Invalid slide number: {slide_no}")
        if slide_ts < 0 or slide_ts > total_duration:
            raise click.UsageError(f"Invalid timestamp: {slide_ts} for slide number: {slide_no}, timestamp must be between 0 and {total_duration}")
        # It is OK to find a duplicate entry.
        if ((slide_no != last_no) and slide_ts <= last_ts) or (slide_no == last_no and slide_ts < last_ts) :
            raise click.UsageError(f"Invalid timestamp: {slide_ts} for slide number: {slide_no}, timestamp must be greater than the last timestamp: ${last_ts}")

        slide_durs.append((last_no, slide_ts - last_ts))
        if entry_no == len(slide_timestamps):
            slide_durs.append((slide_no, total_duration - slide_ts))
        else:
            last_ts = slide_ts
            last_no = slide_no
    # Add one entry for the last slide with no duration. It is weird that this is needed, as we are already adding one for final slide too.
    slide_durs.append((slide_no, None))

    with NamedTemporaryFile(mode = "w", delete = not dry_run) as concat_file:
        click.echo(f"Generating concat file...")
        concat_file.write("ffconcat version 1.0\n")
        for slide_no, slide_dur in slide_durs:
            concat_file.write(f"file {slide_idx[slide_no]}\n")
            if slide_dur is not None:
                concat_file.write(f"duration {slide_dur}\n")

        concat_file.flush()
        if dry_run:
            ffmpeg = partial(sh.echo, "ffmpeg")
            click.echo("Run the following command to generate slides video...")
        else:
            ffmpeg = sh.ffmpeg
            click.echo("Running ffmpeg to generate slides video...")

        video_scale = video_scale.replace("x", ":")
        ffmpeg("-f", "concat", "-safe", "0", "-i", concat_file.name, "-i", audio_file, "-c:a", "copy", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", f"fps=10,scale={video_scale}", "-y", video_out, _out=sys.stdout, _err=sys.stderr, _in=sys.stdin)


def to_timestamp(ts_str: str):
    if ts_str.isdigit():
        return int(ts_str)
    else:
        try:
            sep_count = ts_str.count(":")
            if sep_count:
                if sep_count > 1:
                    raise click.UsageError(f"Invalid timestamp format: {ts_str}, expected min:sec")
                (min_val, sec_val) = ts_str.split(":")
                return int(min_val) * 60 + int(sec_val)
            else:
                return float(ts_str)
        except ValueError as e:
            raise click.UsageError(f"Invalid timestamp value: {ts_str}") from e


if __name__ == '__main__':
    main()
