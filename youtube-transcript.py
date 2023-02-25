import sys

import click
from youtube_transcript_api import YouTubeTranscriptApi


# Return aggregated lines at the specified interval duration
def lines_by_dur(transcript, int_dur):
    cur_st = 0
    cur_text = ""
    next_st = int_dur
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
            cur_text = line_map["text"]
            next_st = cur_st + int_dur


def lines_by_words(transcript, word_count):
    cur_st = 0
    cur_text = ""
    cur_wc = 0
    line_iter = iter(transcript.fetch())
    while True:
        try:
            line_map = next(line_iter)
        except StopIteration:
            line_map = None
        new_wc = line_map and len(line_map['text'].split()) or 0
        if line_map and (cur_wc + new_wc) < word_count:
            cur_st = cur_st or line_map['start']
            cur_text = cur_text + " " + line_map['text']
            cur_wc += new_wc
            continue
        if line_map and (cur_wc + new_wc) >= word_count:
            res_map = {'start': cur_st, 'text': cur_text}
            yield res_map
        if not line_map:
            break
        else:
            cur_st = line_map["start"]
            cur_text = line_map["text"]
            cur_wc = len(cur_text.split())


@click.command()
@click.option("--interval-duration", "--id", "-d", default=60, help="Interval duration for generating timestamps, use 0 to disable and produce raw output")
@click.option("--word-count", "--wc", "-w", default=0, help="Number of words for generating timestamps, applicable when --interval-duration=0")
@click.option("--timestamp-in-seconds", "--tis", "-s", is_flag=True, default=False, help="Specify to see duration in seconds instead of min:sec")
@click.argument("video-id")
def main(interval_duration, timestamp_in_seconds, word_count, video_id):
    # Retrieve the available transcripts
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    # Just use the first transcript, let it raise an exception if none exist.
    transcript = next(iter(transcript_list))
    print("<html><body><table>")
    lines_iter = (interval_duration <= 0 and word_count <= 0) and transcript.fetch() or (
        interval_duration > 0 and lines_by_dur(transcript, interval_duration)) or lines_by_words(transcript, word_count)

    for line_map in lines_iter:
        link_to_tstmp = f"https://youtu.be/{video_id}?t={int(line_map['start'])}"
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
