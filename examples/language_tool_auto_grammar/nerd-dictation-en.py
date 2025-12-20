# https://github.com/ideasman42/nerd-dictation/tree/main/examples
# This example has minimal configuration and lets Language Tool do the work to
# make it look right. (I am not at all affiliated with Language tool, I just
# found it useful to work with nerd-dictation.)
#
# Language Tool is a free service (or local server for the paranoid!) for low
# request volume and I have added it to my nerd-dictation configuration to
# correct and add punctuation where necessary.  I have found that it makes far,
# far less manual editing in the result of the spoken text:
#   https://languagetool.org/
#
# Here is a simple example:
#
# Raw spoken input:
#    can we go to costa rica in june question mark it is for my son's twelfth
#    birthday and i hope we have a lot of fun period
#
# This is the result without editing:
#    Can we go to Costa Rica in June? It is for my son's twelfth birthday and
#    I hope we have a lot of fun.
#
# For which the following rules were applied:
#    Rule: UPPERCASE_SENTENCE_START
#    Rule: EN_SPECIFIC_CASE
#    Rule: MORFOLOGIK_RULE_EN_US
#    Rule: UPPERCASE_SENTENCE_START
#    Rule: I_LOWERCASE
#
# nerd-dictation was invoked as follows:
#    ./nerd-dictation begin --config ./examples/language_tool/nerd-dictation.py
#
# I used the Vosk model vosk-model-en-us-0.22-lgraph, but it probably does not
# matter which model you use.
import subprocess #debug
import time #debug
import string #punctuation check

import re
import requests
from pprint import pprint


class Ending:
    __slots__ = ("spoken", "replacement")

    def __init__(self, spoken: str, replacement: str):
        self.spoken = spoken
        self.replacement = replacement

class ENDINGS:
    EMPTY = Ending("", "")
    DOT = Ending("here stop", ".")
    QUESTION = Ending("here question","?")
    EXCLAMATION = Ending("here exclamation", "!")

    ALL = (DOT, QUESTION, EXCLAMATION)

    @staticmethod
    def rsplit_last_and_replace(text: str):
        """
        Split text at the rightmost occurrence of any ending in ALL.
        Returns (head, ending, tail), and replaces all spoken forms
        in head and tail with their replacement characters.
        """
        head, s, tail = rsplit_last(text, ENDINGS.ALL)

        # Replace all spoken forms in head and tail
        for e in ENDINGS.ALL:
            if e is ENDINGS.EMPTY:
                continue
            # Match optional preceding whitespace + spoken ending
            pattern = re.compile(rf"\s*{re.escape(e.spoken)}")
            head = pattern.sub(e.replacement, head)
            tail = pattern.sub(e.replacement, tail)

        return head.strip(), s, tail.strip()

PUNCTUATION = {
    "coma coma": ",",
    "stop stop": ".",
    "exclamation mark": "!",
    "question mark": "?",
}

CLOSING_PUNCTUATION = {
    "period": ".",

    "comma": ",",
    "karma": ",",
    "calmer": ",",

    "question mark": "?",
    "exclamation mark": '!',

    "colin": ":",
    "semi colon": ";",

    "close quote": '"',
    "close bracket": ')',
    "close brace": '}',
    "close square": ']',
    "close carrot": ">",
    "close tick": "'",
}

OPENING_PUNCTUATION = {
    "open quote": '"',
    "open bracket": '(',
    "open brace": '{',
    "open square": '[',
    "open carrot": '<',
    "close tick": "'",
}

CLEAR = "clear clear"
LT_ITERATIONS=1

# Change this if necessary:
language = "en-US"

def nerd_dictation_process(text, prev_text):
    print("\n\n<<<< before: " + text + f"; prev: {prev_text}")
    if prev_text == text:
        return prev_text

    start = time.perf_counter()
    if CLEAR in text:
        DICTATION_CONTROL.clear_buffer = True
        return ""

    # get the last sentence for language tool and replace ENDING keywords
    head, s, tail = ENDINGS.rsplit_last_and_replace(text)

    # Fix up punctuation first because the grammar parser works better:
    for match, replacement in PUNCTUATION.items():
        pattern = r"\s*" + re.escape(match) + r"(?=\s|$|[.,!?])"
        if head:
            head = re.sub(pattern, replacement, head)
        tail = re.sub(pattern, replacement, tail)

    print("\n\n<<<< after: " + head + "|" + s.replacement + "|" + tail)

    # Iterate langtool while it finds additional changes (or 3 tries):
    tries = LT_ITERATIONS

    while tail:
        new_text = langtool(tail, language)
        if new_text == tail or not tries:
            break
        else:
            tail = new_text

        tries -= 1
    duration = time.perf_counter() - start
    subprocess.run(
        f'DISPLAY=:0.0 notify-send -i "typing-monitor" "LanguageTool" "{tail}\n{duration:.3f}sec"',
        shell=True
    )
    new_text = head + s.replacement + tail
    print(">>>> final: " + new_text + "\n\n")

    return new_text


# Simple API function.  Documentation:
#    https://languagetool.org/http-api/swagger-ui/#!/default/post_check
def langtool(text, language):
    if len(text) == 0 or contains_only_stops(text):
        return text

    r = requests.post(
        "https://api.languagetoolplus.com/v2/check",
        data={
            "text": text,
            "language": language,
            "enabledOnly": "false",
            "level": "default",
            #'level': 'picky', # or be more picky
        },
    )

    orig_len = len(text)
    new_len = 0
    for m in r.json()["matches"]:
        # len(text) can change while iterating due to additions or deletions,
        # which breaks the offset. Adjust the offset if length changes:
        if new_len:
            adj = new_len - orig_len
        else:
            adj = 0

        o = m["offset"] + adj
        n = m["length"]

        print("  Rule: " + m["rule"]["id"])
        if m["rule"]["id"] in ["TOO_LONG_SENTENCE"]:
            # Skip rules from Language Tool that you don't want:
            print("============== langtool skipping ID: " + m["rule"]["id"])

        elif len(m["replacements"]) >= 1:
            # Try the first replacement
            text = text[:o] + m["replacements"][0]["value"] + text[o + n :]

        elif n > 0:
            # No replacement suggestions, but a length is provided so point out
            # the unexpected content with square brackets:
            text = text[:o] + "[" + text[o : o + n + 1] + "]" + text[o + n + 1 :]

        else:
            # If we get here this is probably an unhandled case:
            print("\n\n======== langtool no replacement? " + text)

            # Limit the "replacements" list to prevent huge debug:
            m["replacements"] = m["replacements"][0:3]
            pprint(m)

        new_len = len(text)

    return text

def rsplit_last(text: str, seps):
    positions = [(text.rfind(sep.replacement), sep) for sep in seps]
    pos, sep = max(positions, key=lambda x: x[0]) #check positions only

    if pos == -1:
        return "", ENDINGS.EMPTY, text

    return text[:pos].strip(), sep, text[pos + len(sep.replacement):].strip()

def contains_only_stops(s: str) -> bool:
    return bool(s) and all(c in string.punctuation for c in s)