import logging
import re
import sys

from bs4 import BeautifulSoup
import requests

GAME_FINDER = re.compile("[A-Z][\w\s\.]+\sat\s[A-Z][\w\s\.]+")
TEAM_BREAKER = re.compile("\s+at\s+")
BET_BREAKER = re.compile("\s+by\s+")

logging.basicConfig(stream=sys.stdout, level=logging.WARN)
logger = logging.getLogger(__file__)

# TODO: fill out team mascot, city shorthands, etc.
ALIASES = {}


class Parser(object):
    def __init__(self, url):
        r = requests.get(url)
        bs = BeautifulSoup(r.text, "html.parser")
        comments = bs.find_all("div", class_="comments")
        self.assemble_games(comments[0])
        self.tabulate_votes(comments[1:])
        self.summarize()

    def assemble_games(self, first_comment):
        self.games = {}
        self.teams = {}
        self.locks = {}
        for line in first_comment.text.split("\n"):
            if not line or len(line) > 50:
                continue
            matches = GAME_FINDER.findall(line)
            if matches:
                home, away = TEAM_BREAKER.split(matches[0])
                home = home.lower()
                away = away.lower()
                key = u"%s-%s" % (home, away)
                self.games[key] = {home: [], away: [], "name": matches[0]}
                self.teams[home.lower()] = key
                self.teams[away.lower()] = key
                

    def tabulate_votes(self, comments):
        for c in comments:
            for bet in [bet for bet in c.text.split("\n")
                        if bet and bet.find("posted by") == -1
                        and bet.lower().find(" by ") > -1]:
                bet = bet.lower().strip()
                winner, spread = BET_BREAKER.split(bet)
                # ignore lock comments after the bet
                spread = spread.split(" ")[0]
                try:
                    key = self.teams[winner]
                    self.games[key][winner].append(int(spread))
                    if self.is_lock(bet):
                        self.locks[winner] = self.locks.get(winner, 0) + 1
                except KeyError:
                    logger.warn("Could not find a game for %s (%s)", winner, bet)

    def summarize(self):
        for data in self.games.values():
            results = []
            for k, v in data.items():
                if k == "name":
                    name = v
                else:
                    votes = len(v)
                    average = sum(v) / float(votes) if votes else 0.0
                    results.append("%s: %d votes, %.2f average spread" % (k, votes, average))
            print "%s: %s / %s" % (name, results[0], results[1])
        print "== LOCKS == (TODO: handle bolding)"
        for k, v in self.locks.items():
            print "%s: %d" % (k, v)
            

    def is_lock(self, bet):
        "Really guessing here, need to look at raw HTML for <b>/ <strong> tags"
        return bet.lower().find("lock") > -1 or len(bet) > 30


if __name__ == "__main__":
    p = Parser("http://www.sportsfilter.com/news/20820/nfl-pick-em-week-4-first-place")