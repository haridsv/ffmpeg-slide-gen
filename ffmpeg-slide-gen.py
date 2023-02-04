import sys
from typing import Tuple
from tempfile import NamedTemporaryFile

import click
from sh import mediainfo, ffmpeg


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
@click.option("--slide-count", "-c", required=True, help="Number of slides")
@click.option("--slides", "-i", nargs=0, required=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="List of image filenames as an ordered sequence")
@click.option("--slide-ts", "--ts", "-s", "slide_timestamps", multiple=True, required=True, type=(int, int), help="Pair of integers: slide timestamp")
@click.option("--audio-file", "-a", required=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Specify the path to the audio file")
@click.option("--video-out", "-o", required=True, help="Specify the path for the output video file")
def main(slide_count, slides, slide_timestamps, audio_file, video_out):
    """
    Generate FFMpeg demux concat file from specified slides and timestamps.
    See: https://superuser.com/a/619843/26006
    """
    slide_idx = dict(enumerate(isinstance(slides, Tuple) and slides or [slides], start=1))
    total_duration = int(mediainfo('--Inform=Audio;%Duration%', audio_file)) / 1000

    slide_durs = []
    last_ts = -1
    for slide_no, slide_ts in slide_timestamps:
        if slide_no not in slide_idx:
            raise click.UsageError(f"Invalid slide number: {slide_no}")
        if slide_ts < 0 or slide_ts > total_duration:
            raise click.UsageError(f"Invalid timestamp: {slide_ts} for slide number: {slide_no}, timestamp must be between 0 and {total_duration}")
        if slide_ts <= last_ts:
            raise click.UsageError(f"Invalid timestamp: {slide_ts} for slide number: {slide_no}, timestamp must be greater than the last timestamp: ${last_ts}")

        slide_durs.append((slide_no, slide_ts - (last_ts >= 0 and last_ts or 0)))
        last_ts = slide_ts
    slide_durs.append((slide_no, None))

    with NamedTemporaryFile(mode="w") as concat_file:
        print(f"Writing concat file to the tempfile: {concat_file.name}")
        concat_file.write("ffconcat version 1.0\n")
        for slide_no, slide_dur in slide_durs:
            concat_file.write(f"file {slide_idx[slide_no]}\n")
            if slide_dur is not None:
                concat_file.write(f"duration {slide_dur}\n")

        concat_file.flush()
        print("Generating slide video")
        ffmpeg("-f", "concat", "-safe", "0", "-i", concat_file.name, "-i", audio_file, "-c:a", "copy", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "fps=10, scale=1280:720", "-y", video_out, _out=sys.stdout, _err=sys.stderr, _in=sys.stdin)


if __name__ == '__main__':
    main()
