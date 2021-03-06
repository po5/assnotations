import argparse
import xml.etree.ElementTree
import datetime
import textwrap
import math
import json
import glob

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--format", default="ass", choices=["ass", "json"], help="Output format")
parser.add_argument("-g", "--glob", nargs='?', help="Glob")
parser.add_argument("-x", "--width", default=1440, type=int, help="Script width")
parser.add_argument("-y", "--height", default=1080, type=int, help="Script height")
parser.add_argument("files", nargs="*", default=[], help="Files to parse")

args = parser.parse_args()

base = r"""[Script Info]
; Script generated by assify
; https://github.com/po5/assify
Title: YouTube annotations{3}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {0}
PlayResY: {1}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1
Style: Annotations,Arial,{2},&H00000000,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Icons,Arial,{2},&H00000000,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,3,1,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def color(el, attr):
    if el.attrib.get(attr):
        return f"{int(el.attrib.get(attr)):06x}".upper()

def timestamp_to_seconds(t):
    return sum(float(n) * m for n, m in zip(reversed(t.split(":")), (1, 60, 3600)))

def parse(filename):
    tree = xml.etree.ElementTree.parse(filename)
    root = tree.getroot()

    video_id = None
    annotations = {}
    highlight_text = {}

    for child in root[0]:
        x = y = w = h = sx = sy = fg_color = bg_color = border_color = border_alpha = border_width = bg_alpha = gloss = text_size = highlight_font_color = highlight_width = effects = url = None

        segment = child.find("segment")
        moving_region = segment.find("movingRegion")
        box = moving_region.findall("rectRegion")
        if not box:
            box = moving_region.findall("anchoredRegion")
        if box:
            start = min(box[0].get("t"), box[1].get("t"))
            end = max(box[0].get("t"), box[1].get("t"))
            if start == "never":
                start = None
            else:
                start = timestamp_to_seconds(start)
            if end == "never":
                end = None
            else:
                end = timestamp_to_seconds(end)
            x, y, w, h = map(float, (box[0].get(i) for i in ("x","y","w","h")))
            sx = box[0].get("sx", None)
            if sx:
                sx = float(sx)
            sy = box[0].get("sy", None)
            if sy:
                sy = float(sy)
        else:
            start = end = None
        appearance = child.find("appearance")
        if appearance is not None:
            fg_color = color(appearance, "fgColor")
            bg_color = color(appearance, "bgColor")
            border_color = color(appearance, "borderColor")
            highlight_font_color = color(appearance, "highlightFontColor")
            highlight_width = appearance.attrib.get("highlightWidth", None)
            if highlight_width:
                highlight_width = int(highlight_width)
            if appearance.attrib.get("borderAlpha"):
                border_alpha = 100 - float(appearance.attrib.get("borderAlpha")) * 100
            if appearance.attrib.get("bgAlpha"):
                bg_alpha = 100 - float(appearance.attrib.get("bgAlpha")) * 100
            border_width = appearance.attrib.get("borderWidth", None)
            if border_width:
                border_width = int(border_width)
            gloss = appearance.attrib.get("gloss", None)
            if gloss:
                gloss = int(gloss)
            text_size = appearance.attrib.get("textSize", None)
            if text_size:
                text_size = float(text_size)
            font_weight = appearance.attrib.get("fontWeight", None)
            effects = appearance.attrib.get("effects", None) or None
        else:
            fg_color = "000000"
            bg_color = "FFFFFF"
            bg_alpha = 100 - 80
        if child.find("action"):
            url = child.find("action").find("url").get("value", None)
        annotation = {
        "id": int(child.attrib.get("id", None).replace("annotation_", "")) if "id" in child.attrib else None,
        "author": child.attrib.get("author", None),
        "style": child.attrib.get("style", None),
        "type": child.attrib.get("type", None),
        "logable": child.attrib.get("logable", None),
        "itct": child.attrib.get("itct", None) or None,
        "text": getattr(child.find("TEXT"), "text", None),
        "start": start,
        "end": end,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "sx": sx,
        "sy": sy,
        "fg_color": fg_color,
        "bg_color": bg_color,
        "bg_alpha": bg_alpha,
        "border_color": border_color,
        "border_alpha": border_alpha,
        "border_width": border_width,
        "gloss": gloss,
        "text_size": text_size,
        "font_weight": font_weight,
        "effects": effects,
        "highlight_font_color": highlight_font_color,
        "highlight_width": highlight_width,
        "url": url
        }
        if annotation["type"] == "highlight" and annotation["id"] in highlight_text:
            annotation["text"] = highlight_text[annotation["id"]]
            del highlight_text[annotation["id"]]
        if not video_id and "a-v=" in child.attrib.get("log_data", ""):
            video_id = child.attrib.get("log_data", "").split("a-v=")[1].split("&")[0] or None
        if annotation["style"] == "highlightText" and annotation["text"]:
            main_annotation_id = int(segment.attrib.get("spaceRelative", None).replace("annotation_", "")) if "spaceRelative" in segment.attrib else None
            if main_annotation_id not in annotations:
                if main_annotation_id not in highlight_text:
                    highlight_text[main_annotation_id] = annotation["text"]
                else:
                    highlight_text[main_annotation_id] += "\n" + annotation["text"]
                continue
            if not annotations[main_annotation_id]["text"]:
                annotations[main_annotation_id]["text"] = annotation["text"]
            else:
                annotations[main_annotation_id]["text"] += "\n" + annotation["text"]
            continue
        annotations[annotation["id"]] = annotation
    return {"video_id": video_id, "annotations": sorted(annotations.values(), key=lambda k: k["start"] or -1), "highlight_text": highlight_text}

def percent_to_pixels(size, percent):
    return size * percent / 100;

def rgb_to_bgr(rgb):
    return f"{rgb[-2:]}{rgb[-4:-2]}{rgb[-6:-4]}"

def alpha_to_hex(alpha):
    return f"{int(255 * alpha / 100):02x}".upper()

def wrap(words, length):
    return " ".join([r"\N".join([r"\N".join(textwrap.wrap(line.rstrip(), width=length, break_long_words=True)) for line in word.split(r"\N")]) for word in words.split(" ")])

def scale_drawing(scale, drawing):
    return " ".join(map(lambda i : str((float(i) * scale) or 0) if i.replace(".", "", 1).replace("-", "", 1).isdigit() else i, drawing.split(" ")))

def to_ass(filename, width=100, height=100):
    parsed = parse(filename)
    subs = base.format(width, height, 51/1920*width, f" for {parsed['video_id'] or ''}")
    for annotation in parsed["annotations"]:
        if None in (annotation["start"], annotation["end"]):
            continue
        if None in (annotation["x"], annotation["y"], annotation["w"], annotation["h"]):
            continue
        if None in (annotation["bg_color"],):
            continue
        x = percent_to_pixels(width, annotation["x"])
        y = percent_to_pixels(height, annotation["y"])
        w = percent_to_pixels(width, annotation["w"])
        h = percent_to_pixels(height, annotation["h"])
        x2 = x+w
        y2 = y+h
        x_padding = percent_to_pixels(width, 1.5) /2
        y_padding = percent_to_pixels(height, 1.5) /2
        y_outline = percent_to_pixels(height, .5)
        clip_outline = y_outline
        line = f"Dialogue: 0,{(str(datetime.timedelta(seconds=annotation['start']))+'.00')[:10]},{(str(datetime.timedelta(seconds=annotation['end']))+'.00')[:10]},"
        bg_line = line + r"Annotations,{},0,0,0,,{{\pos(0,0)".format(annotation['author'] or '')
        if annotation["bg_alpha"] is None:
            annotation["bg_alpha"] = 100 - 80
        bg_line += r"\1a&H"+alpha_to_hex(annotation["bg_alpha"])+"&"
        if annotation["bg_color"] != "000000":
            bg_line += r"\1c&H"+rgb_to_bgr(annotation["bg_color"])+"&"
        if annotation["type"] == "highlight":
            clip_outline = clip_outline / 2
            bg_line += r"\iclip({},{},{},{})".format(x + clip_outline, y + clip_outline, x2 - clip_outline, y2 - clip_outline)
            annotation["fg_color"] = annotation["fg_color"] or annotation["highlight_font_color"] or annotation["bg_color"]
        if None not in (annotation["sx"], annotation["sy"]):
            sx = percent_to_pixels(width, annotation["sx"])
            sy = percent_to_pixels(height, annotation["sy"])
            bg_line += speech_bubble(x, y, x2, y2, w, h, sx, sy)
        else:
            bg_line += r"\p1}}m {0} {1} l {2} {1} {2} {3} {0} {3}{{\p0}}".format(x, y, x2, y2)
        bg_line += "\n"
        fg_line = ""
        if (annotation["text"] or "").strip():
            fg_line = line + r"Annotations,{},{},{},0,,{{\pos({},{})".format(annotation['author'] or '', int(x)+1 if (int(width-x2) != 0 or annotation["h"] > 8) else 0, math.ceil(width-x2+x_padding), x+x_padding, y+y_padding)
            fg_line += r"\clip({},{},{},{})".format(x + clip_outline, y + clip_outline, x2 - clip_outline, y2 - clip_outline)
            if annotation["fg_color"] not in ("000000", None):
                fg_line += r"\1c&H{}&".format(rgb_to_bgr(annotation["fg_color"]))
            if (annotation["text_size"] or 3.6107) != 3.6107:
                fg_line += r"\fs" + str(51/1920*width / 3.6107 * annotation["text_size"])
            fg_line += "}"
            if annotation["text"] != annotation["text"].lstrip():
                annotation["text"] = "\u200b" + annotation["text"]
            fg_line += wrap(annotation["text"].rstrip().replace("\n\n", r"\N\N\N\N\N").replace("\n", r"\N"), math.ceil(18 / 424 * w / (width / 1440)) or 1)
            fg_line += "\n"
        if annotation["url"]:
            scale = height / 1.2 / 1440
            icon = scale_drawing(scale, "m 4.15 0 l 18.85 0 18.85 10.3 10.2 10.3 10.2 50.65 51.25 50.65 51.25 42.4 61.4 42.4 61.4 60.95 0 60.95 0 0 4.15 0 4.15 0 m 61.45 0 l 26.65 0 38.5 11.6 21.75 28.35 32.4 38.95 49.15 22.2 61.45 34.25 61.45 0 61.45 0")
            fg_line += line + f"Icons,{annotation['author'] or ''},0,0,0,,{{"
            if annotation["fg_color"] not in ("000000", None):
                fg_line += r"\1c&H{}&".format(rgb_to_bgr(annotation["fg_color"]))
            fg_line += r"\3a&H"+alpha_to_hex(annotation["bg_alpha"])+"&"
            if annotation["bg_color"] != "000000":
                fg_line += r"\3c&H"+rgb_to_bgr(annotation["bg_color"])+"&"
            fg_line += r"\pos(" + str((x2 - 72 * scale) or 0) + "," + str((y2 - 72 * scale) or 0) + r")\p1}" + icon + r"{\p0}"
            fg_line += "\n"
        subs += bg_line
        subs += fg_line
    return subs

h_base_start_multiplier = 0.17379070765180116
h_base_end_multiplier = 0.14896346370154384
v_base_start_multiplier = 0.12
v_base_end_multiplier = 0.3

def get_point_direction(x, y, width, height, point_x, point_y, direction_padding=20):
    if point_x > ((x + width) - (width / 2)) and point_y > y + height:
       return "br"
    elif point_x < ((x + width) - (width / 2)) and point_y > y + height:
       return "bl"
    elif point_x > ((x + width) - (width / 2)) and point_y < (y - direction_padding):
       return "tr"
    elif point_x < ((x + width) - (width / 2)) and point_y < y:
       return "tl"
    elif point_x > (x + width) and point_y > (y - direction_padding) and point_y < ((y + height) - direction_padding):
       return "r"
    elif point_x < x and point_y > y and point_y < (y + height):
       return "l"

def speech_bubble(x, y, x2, y2, width, height, point_x, point_y, direction_padding=20):
    point_direction = get_point_direction(x, y, width, height, point_x, point_y, direction_padding)
    bubble = ""

    if point_direction == "br":
        base_start_x = width - ((width * h_base_start_multiplier) * 2)
        base_end_x = base_start_x + (width * h_base_end_multiplier)
        base_start_y = height
        base_end_y = height
        triangle = f" {base_end_x+x} {base_end_y+y} {point_x} {point_y} {base_start_x+x} {base_start_y+y}"
        bubble = r"\p1}}m {0} {1} l {2} {1} {2} {3}{4} {0} {3}{{\p0}}".format(x, y, x2, y2, triangle)

    elif point_direction == "bl":
        base_start_x = width * h_base_start_multiplier
        base_end_x = base_start_x + (width * h_base_end_multiplier)
        base_start_y = height
        base_end_y = height
        triangle = f" {base_end_x+x} {base_end_y+y} {point_x} {point_y} {base_start_x+x} {base_start_y+y}"
        bubble = r"\p1}}m {0} {1} l {2} {1} {2} {3}{4} {0} {3}{{\p0}}".format(x, y, x2, y2, triangle)

    elif point_direction == "tr":
        base_start_x = width - ((width * h_base_start_multiplier) * 2)
        base_end_x = base_start_x + (width * h_base_end_multiplier)
        y_offset = y - point_y
        triangle = f" {base_start_x+x} {y} {point_x} {point_y} {base_end_x+x} {y}"
        bubble = r"\p1}}m {0} {1} l{4} {2} {1} {2} {3} {0} {3}{{\p0}}".format(x, y, x2, y2, triangle)

    elif point_direction == "tl":
        base_start_x = width * h_base_start_multiplier
        base_end_x = base_start_x + (width * h_base_end_multiplier)
        y_offset = y - point_y
        triangle = f" {base_start_x+x} {y} {point_x} {point_y} {base_end_x+x} {y}"
        bubble = r"\p1}}m {0} {1} l{4} {2} {1} {2} {3} {0} {3}{{\p0}}".format(x, y, x2, y2, triangle)

    elif point_direction == "r":
        x_offset = point_x - (x + width)
        base_start_x = width
        base_end_x = width
        base_start_y = height * v_base_start_multiplier
        base_end_y = base_start_y + (height * v_base_end_multiplier)
        triangle = f" {base_start_x+x} {base_start_y+y} {point_x} {point_y} {base_end_x+x} {base_end_y+y}"
        bubble = r"\p1}}m {0} {1} l {2} {1}{4} {2} {3} {0} {3}{{\p0}}".format(x, y, x2, y2, triangle)

    elif point_direction == "l":
        x_offset = x - point_x
        base_start_y = height * v_base_start_multiplier
        base_end_y = base_start_y + (height * v_base_end_multiplier)
        triangle = f" {x} {base_end_y+y} {point_x} {point_y} {x} {base_start_y+y}"
        bubble = r"\p1}}m {0} {1} l {2} {1} {2} {3} {0} {3}{4}{{\p0}}".format(x, y, x2, y2, triangle)

    return bubble

def to_json(filename):
    return json.dumps(parse(filename))

if args.glob:
    args.files.extend(glob.glob('**/*.xml', recursive=True))

for file in args.files:
    if args.format == "json":
        out = to_json(file)
    else:
        out = to_ass(file, args.width, args.height)
    print(out, end="")
