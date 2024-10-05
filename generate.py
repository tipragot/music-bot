import re
import sys
from unicodedata import normalize, combining
from difflib import SequenceMatcher
from random import choice, choices
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--prompt', type=str, required=False)
parser.add_argument('--copy', type=str, required=False)
args = parser.parse_args()

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def strip_accents(string):
    return "".join(c for c in normalize("NFD", string) if not combining(c))

messages: list[list[str]] = []
with open("messages.txt", "r", encoding="utf-8") as f:
    for line in f.readlines():
        message = line.strip()
        while '  ' in message: message = message.replace('  ', ' ')
        if args.copy:
            author = message.split(": ")[0]
            if author != args.copy: continue
        start_index = message.index(": ") + 2
        words: list[str] = []
        for word in message[start_index:].split(" "):
            if not word.startswith("https://") and not word.startswith("<"):
                word = strip_accents(word.lower())
                # word = word.lower()
                words.append(word)
                # words.extend(word_tokenize(word, language="french"))
            else: words.append(word)
        words.append("")
        messages.append(words)

CONTEXT_SIZE = 5
TEMPERATURE = 12
PATHS = 5
MAX_LENGTH = 20
MAX_WORD_COUNT = 50

next_words: dict[str, list[str]] = {}
for words in messages:
    for i in range(len(words) - 1):
        for j in range(1, CONTEXT_SIZE+1):
            if i + j >= len(words): break
            context = " ".join(words[i:i+j])
            next_words.setdefault(context, []).append(words[i+j])

def get_next_words(context: list[str], count: int):
    results: dict[str, int] = {}
    for i in range(len(context)):
        current_context = " ".join(context[i:])
        if current_context in next_words:
            for next_word in next_words[current_context]:
                if next_word not in results: results[next_word] = 0
                results[next_word] += (len(context) - i) ** TEMPERATURE
    for word in context:
        if word in results:
            results[word] /= TEMPERATURE
    words = list(results.keys())
    weights = [results[word] for word in words]
    return set(choices(words, weights, k=count))

def create_messages(context: list[str], results: list[list[str]], depth: int = 0):
    if context[-1] == "":
        results.append(context)
        return
    if depth > MAX_WORD_COUNT: return
    words = get_next_words(context, count=PATHS)
    for word in words:
        create_messages(context + [word], results, depth+1)
        if len(results) >= MAX_LENGTH: break

def get_best_message(generated_messages: list[list[str]]):
    scores = []
    for generated_message in generated_messages:
        score = 0
        for message in messages:
            score += similar(generated_message, message)
        score /= len(generated_message)
        scores.append(score)
        # print(score, ":", generated_message)
    return generated_messages[scores.index(min(scores))]


results = []
message = choice(messages)
context = message[:min(2, len(message))]
if args.prompt:
    context = args.prompt.strip().split(" ")
# context = ["je"]
create_messages(context, results)
print(" ".join(get_best_message(results)))
