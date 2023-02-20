import sys

import click
from youtube_transcript_api import YouTubeTranscriptApi


# Return aggregated lines at the specified interval duration
def lines(transcript, int_dur=60):
    cur_st = 0
    next_st = int_dur
    cur_text = ""
    line_iter = iter(transcript.fetch())
    while True:
        try:
            line_map = next(line_iter)
        except StopIteration:
            line_map = None
        if line_map and line_map['start'] < next_st:
            cur_st = cur_st or line_map['start']
            cur_text = cur_text + " " + line_map['text']
            continue
        elif cur_text:
            res_map = {'start': cur_st, 'text': cur_text}
            yield res_map
        if not line_map:
            break
        else:
            cur_st = line_map["start"]
            next_st = cur_st + int_dur
            cur_text = line_map["text"]


@click.command()
@click.option("--interval-duration", "--id", "-d", default=60, help="Interval duration for generating timestamps, use 0 to disable and produce raw output")
@click.option("--timestamp-in-seconds", "--tis", "-s", is_flag=True, default=False, help="Specify to see duration in seconds instead of min:sec")
@click.argument("video-id")
def main(interval_duration, timestamp_in_seconds, video_id):
    # Retrieve the available transcripts
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    # Just use the first transcript, let it raise an exception if none exist.
    transcript = next(iter(transcript_list))
    print("<html><body><table>")
    lines_iter = interval_duration <= 0 and transcript.fetch() or lines(transcript, interval_duration)
    for line_map in lines_iter:
        link_to_tstmp = f"https://youtu.be/{video_id}?t={line_map['start']}"
        if timestamp_in_seconds:
            tstmp_str = str(int(line_map['start']))
        else:
            st_min = int(line_map['start'] / 60)
            st_sec = int(line_map['start'] - st_min * 60)
            tstmp_str = ("%2d:%-2d" % (st_min, st_sec)).replace(" ", "&nbsp;")
        print("""<tr><td  style="vertical-align:top"><a href="%s">%s</a></td><td>%s</td></tr>""" % (link_to_tstmp, tstmp_str, line_map['text']))
    print("</table></html></body>")


if __name__ == '__main__':
    main()
