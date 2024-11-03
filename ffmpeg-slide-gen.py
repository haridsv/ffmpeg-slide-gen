import sys
import re
from functools import partial
from operator import itemgetter
from typing import Tuple
from tempfile import NamedTemporaryFile
from time import gmtime, strftime

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
@click.option("--slide-count", "-c", help="Number of slides.")
@click.option("--slides", "-i", nargs=0, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="List of image filenames as an ordered sequence.")
@click.option("--text-timestamp", "--txt", "-t", "text_timestamps", multiple=True, type=(str, str), help="Pair of: <timestamp slide-text>. Timestamp can be in seconds or [hh:]mm:ss. Do not mix with --slide-timestamp/--vlc-playlist-file options.")
@click.option("--slide-timestamp", "--ts", "-s", "slide_timestamps", multiple=True, type=(int, str), help="Pair of: <slide-number timestamp>. Timestamp can be in seconds or [hh:]mm:ss. Not needed if --vlc-playlist-file is specified.")
@click.option("--vlc-playlist-file", "--m3u", "-b", type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Specify the path to the m3u file to extract bookmarks as slide timestamps. Not needed if --slide-timestamps is specified.")
@click.option("--audio-file", "-a", required=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Specify the path to the audio file.")
@click.option("--ffmpeg-audio-opts", "-fao", default="'-c:a copy'", show_default=True, help="Specify the ffmpeg options to be used for audio track, e.g., '-ar 44100'.")
@click.option("--video-out", "-o", required=True, help="Specify the path for the output video file.")
@click.option("--video-scale", "-vs", default="1280:720", show_default=True, help="Specify an alternative scale for output video")
@click.option("--dry-run", "-n", is_flag=True, default=False, help="Enable dry-run mode, generates the concat file and prints the ffmpeg command without actually running it.")
def main(slide_count, slides, text_timestamps, slide_timestamps, vlc_playlist_file, audio_file, ffmpeg_audio_opts, video_out, video_scale, dry_run):
    """
    Generate FFMpeg demux concat file from specified slides and timestamps.
    See: https://superuser.com/a/619843/26006
    """
    if slide_timestamps and vlc_playlist_file:
        raise click.UsageError("--slide-timestamps and --vlc-playlist-file are mutually exclusive options")
    if not (slide_timestamps or vlc_playlist_file or text_timestamps):
        raise click.UsageError("One of the --slide-timestamp, --vlc-playlist-file and --text-timestamp options must be specified")

    total_duration = int(sh.mediainfo('--Inform=Audio;%Duration%', audio_file)) / 1000
    click.echo(f"Total duration of the video will be: {total_duration} seconds")

    if slide_timestamps or vlc_playlist_file:
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
            slide_timestamps = [(slide_no, to_seconds(slide_ts)) for slide_no, slide_ts in slide_timestamps]

        slide_idx = dict(enumerate(isinstance(slides, Tuple) and slides or [slides], start=1))

        slide_durs = []
        last_no = last_ts = -1 # Start with invalid values
        for entry_no, (slide_no, slide_ts) in enumerate(sorted(slide_timestamps, key=itemgetter(1)), start=1):
            if slide_no not in slide_idx:
                raise click.UsageError(f"Invalid slide number: {slide_no}")
            if slide_ts < 0 or slide_ts > total_duration:
                raise click.UsageError(f"Invalid timestamp: {slide_ts} for slide number: {slide_no}, timestamp must be between 0 and {total_duration}")
            # It is OK to find a duplicate entry.
            if (slide_no != last_no and slide_ts <= last_ts) or (slide_no == last_no and slide_ts < last_ts):
                raise click.UsageError(f"Invalid timestamp: {slide_ts} for slide number: {slide_no}, timestamp must be greater than the last timestamp: {last_ts}")

            slide_durs.append((last_no > 0 and last_no or 1, slide_ts - (last_ts > 0 and last_ts or 0)))
            if entry_no == len(slide_timestamps):
                slide_durs.append((slide_no, total_duration - slide_ts))
            else:
                last_ts = slide_ts
                last_no = slide_no
        slide_durs = [dur for dur in slide_durs if dur[1]] # Remove any 0 duration slides.
        # Add one entry for the last slide with no duration. It is weird that this is needed, as we are already adding one for final slide too.
        slide_durs.append((slide_no, None))

    ffmpeg_audio_opts = ffmpeg_audio_opts and ffmpeg_audio_opts.split() or ["-c:a", "copy"]
    with NamedTemporaryFile(mode = "w", delete = not dry_run) as tmp_file:
        if slide_timestamps or vlc_playlist_file:
            click.echo(f"Generating concat file...")
            tmp_file.write("ffconcat version 1.0\n")
            for slide_no, slide_dur in slide_durs:
                tmp_file.write(f"file {slide_idx[slide_no]}\n")
                if slide_dur is not None:
                    tmp_file.write(f"duration {slide_dur}\n")

            tmp_file.flush()

            video_scale = video_scale.replace("x", ":")
            ffmpeg_args = ("-f", "concat", "-safe", "0", "-i", tmp_file.name, "-i", audio_file, *ffmpeg_audio_opts, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", f"fps=10,scale={video_scale}", "-y", video_out)
        else:
            click.echo(f"Generating subs file...")
            text_timestamps += ((str(total_duration), None),)
            cnt = 1
            for st, en in zip(text_timestamps[:-1], text_timestamps[1:]):
                tmp_file.write(f"{cnt}\n{to_hh_mm_ss(st[0])},000 --> {to_hh_mm_ss(en[0])},000\n{st[1]}\n\n")
                cnt += 1
            tmp_file.flush()

            video_scale = video_scale.replace(":", "x")
            ffmpeg_args = ("-i", audio_file, "-f", "lavfi", "-i", f"color=c=white:s={video_scale}:d={total_duration}:r=1",
                           "-vf", f"subtitles={tmp_file.name}:force_style='Alignment=10,FontSize=26,PrimaryColour=black,SecondaryColour=white,Fontname=Arial,Spacing=0.2,Outline=0'",
                           *ffmpeg_audio_opts, "-ar", "44100", "-y", video_out,)

        if dry_run:
            ffmpeg = partial(sh.echo, "ffmpeg")
            click.echo("Run the following command to generate slides video...")
        else:
            ffmpeg = sh.ffmpeg
            click.echo("Running ffmpeg to generate slides video...")

        ffmpeg(*ffmpeg_args, _out=sys.stdout, _err=sys.stderr, _in=sys.stdin)


def to_seconds(ts_str: str) -> float:
    if ts_str.isdigit():
        return int(ts_str)
    else:
        try:
            sep_count = ts_str.count(":")
            if sep_count:
                if sep_count > 2:
                    raise click.UsageError(f"Invalid timestamp format: {ts_str}, expected min:sec")
                (hr_val, min_val, sec_val) = (["0"] + ts_str.split(":"))[-3:]
                return int(hr_val) * 60 * 60 + int(min_val) * 60 + int(sec_val)
            else:
                return float(ts_str)
        except ValueError as e:
            raise click.UsageError(f"Invalid timestamp value: {ts_str}") from e


def to_hh_mm_ss(ts_str: str) -> str:
    sep_count = ts_str.count(":")
    if sep_count:
        if sep_count > 2:
            raise click.UsageError(f"Invalid timestamp format: {ts_str}, expected min:sec")
        return sep_count == 2 and ts_str or "00:" + ts_str
    else:
        if ts_str.isdigit():
            seconds = int(ts_str)
        else:
            try:
                seconds = float(ts_str)
            except ValueError as e:
                raise click.UsageError(f"Invalid timestamp value: {ts_str}") from e

        return strftime("%H:%M:%S", gmtime(seconds))


if __name__ == '__main__':
    main()
