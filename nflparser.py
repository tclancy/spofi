import argparse
import logging
import re
import sys

from bs4 import BeautifulSoup
import requests

MIN_GAMES_IN_WEEK = 4
GAME_FINDER = re.compile(r"[A-Z][\w\s\.]+\sat\s[A-Z][\w\s\.]+")
MATCHUP_SPLITTER = re.compile(r"<br\s*/?>")
TEAM_BREAKER = re.compile(r"\s+at\s+")
BET_BREAKER = re.compile(r"\s+by\s+")
SPREAD_CLEANER = re.compile(r"[^\d]+")
PUNCTUATION_CLEANER = re.compile(r"\.")

logging.basicConfig(stream=sys.stdout, level=logging.WARN)
logger = logging.getLogger(__file__)

# fill out team mascot, city shorthands, etc.
ALIASES = {
    "nyj": "new york jets",
    "nyg": "new york giants",
    "jets": "new york jets",
    "giants": "new york giants",
    "ny jets": "new york jets",
    "ny giants": "new york giants",
    "n.y. jets": "new york jets",
    "n.y. giants": "new york giants",
    # ugh
    "new york football giants": "new york giants",
    "kc": "kansas city",
    "kan": "kansas city",
    "chiefs": "kansas city",
    "ne": "new england",
    "newengland": "new england",
    "pats": "new england",
    "patriots": "new england",
    "ind": "indianapolis",
    "colts": "indianapolis",
    "indy": "indianapolis",
    "phi": "philadelphia",
    "philly": "philadelphia",
    "eagles": "philadelphia",
    "pit": "pittsburgh",
    "steelers": "pittsburgh",
    "car": "carolina",
    "panthers": "carolina",
    "min": "minnesota",
    "vikings": "minnesota",
    "vikes": "minnesota",
    "cle": "cleveland",
    "browns": "cleveland",
    "bal": "baltimore",
    "ravens": "baltimore",
    "hou": "houston",
    "texans": "houston",
    "ari": "arizona",
    "cardinals": "arizona",
    "mia": "miami",
    "dolphins": "miami",
    "sea": "seattle",
    "seahawks": "seattle",
    "den": "denver",
    "broncos": "denver",
    "gb": "green bay",
    "packers": "green bay",
    "pack": "green bay",
    "rams": "st louis",
    "stl": "st louis",
    "atl": "atlanta",
    "falcons": "atlanta",
    "cardinals": "arizona",
    "ari": "arizona",
    "buf": "buffalo",
    "bills": "buffalo",
    "cin": "cincinnati",
    "bengals": "cincinnati",
    "bungles": "cincinnati",
    "ten": "tennesse",
    "titans": "tennesse",
    "saints": "new orleans",
    "no": "new orleans",
    "chargers": "san diego",
    "sd": "san diego",
}


class Parser(object):
    def __init__(self, url):
        r = requests.get(url)
        bs = BeautifulSoup(r.text, "html.parser")
        comments = bs.find_all("div", class_="comments")
        self.top_vote_count = 0
        self.most_votes = 0
        self.top_locks = [("Nobody", 0)]
        self.assemble_games(comments[0])
        self.tabulate_votes(comments[1:])
        self.analyze()
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
                home = PUNCTUATION_CLEANER.sub("", home.lower())
                away = PUNCTUATION_CLEANER.sub("", away.lower())
                key = u"%s-%s" % (home, away)
                self.games[key] = {home: [], away: [], "name": matches[0]}
                self.teams[home.lower()] = key
                self.teams[away.lower()] = key

    def tabulate_votes(self, comments):
        for c in comments:
            if c.text.count("\n") < MIN_GAMES_IN_WEEK:
                raw = MATCHUP_SPLITTER.split(c.decode_contents(formatter="html"))
            else:
                raw = c.text.split("\n")
            if len(raw) < MIN_GAMES_IN_WEEK:
                logger.warn(u"Skipping this as too short: %s", c.text)
            for bet in [bet for bet in raw
                        if bet and bet.lower().find("posted by") == -1
                        and bet.lower().find(" by ") > -1]:
                bet = bet.lower().strip()
                try:
                    winner, spread = BET_BREAKER.split(bet)
                except ValueError:
                    logger.error(u"Could not parse %s", bet)
                    continue
                winner = self.get_normalized_team(winner)
                # ignore lock comments after the bet, clean out punctuation next to bet
                spread = SPREAD_CLEANER.sub("", spread.split(" ")[0])
                try:
                    key = self.teams[winner]
                    try:
                        self.games[key][winner].append(int(spread))
                    except ValueError:
                        # mainly people writing "by seven"
                        logger.warn(u"Could not parse spread for %s", bet)
                    if self.is_lock(bet):
                        self.locks[winner] = self.locks.get(winner, 0) + 1
                except KeyError:
                    logger.warn(u"Could not find a game for \"%s\": (%s)", winner, bet)

    def get_normalized_team(self, team):
        """
        Remove content with "lock" in it
        Look for alternate team name in ALIASES list
        Remove parenthetical asides
        When all else fails, start splitting on spaces until you find it somewhere
        TODO: handle "new york" problem
        """
        original = team
        team = PUNCTUATION_CLEANER.sub("", team)
        team = re.sub(r"\s*lock\s*", "", team)
        team = re.sub(r"\s*\(.*\)\s*", "", team)
        team = ALIASES.get(team, team)
        if team not in self.teams:
            words = original.split(" ")
            lookup = ""
            for word in words:
                lookup += " %s" % word
                lookup = lookup.strip()
                logger.debug("Trying %s|||", lookup)
                if lookup in self.teams:
                    team = lookup
                    break
                if lookup in ALIASES:
                    team = lookup
                    break
        return team

    def analyze(self):
        """
        A. we could do a lot better on the function name here
        B. find the total vote counts for games, so we can look for games under that # (NY)
        C. look for game(s) that are the biggest "lock" of the week
        """
        for data in self.games.values():
            for k, v in data.items():
                if k == "name":
                    continue
                # man this is a shit way to do this
                current_max = self.top_locks[0][1]
                votes = len(v)
                self.most_votes = max(self.most_votes, votes)
                if votes > current_max:
                    self.top_locks = [(k, votes)]
                elif votes == current_max:
                    self.top_locks.append((k, votes))

    def summarize(self):
        """
        Show how many people voted for each side and what the average spread on each side was
        """
        for data in self.games.values():
            results = []
            total_votes = 0
            for k, v in data.items():
                if k == "name":
                    name = v
                else:
                    votes = len(v)
                    total_votes += votes
                    average = sum(v) / float(votes) if votes else 0.0
                    results.append("%s: %d votes, %.2f average spread" % (k, votes, average))
            print u"%s: %s / %s%s" % (name, results[0], results[1], " Missing votes" if total_votes < self.most_votes else "")
        print u"== LOCKS == (TODO: handle bolding)"
        for k, v in self.locks.items():
            print u"%s: %d" % (k, v)
        print u"== BIG WINNER%s ==" % ("S" if len(self.top_locks) != 1 else "")
        for team, _ in self.top_locks:
            print team
        

    def is_lock(self, bet):
        "Really guessing here, need to look at raw HTML for <b>/ <strong> tags"
        return bet.lower().find("lock") > -1 or len(bet) > 30


if __name__ == "__main__":
    argument = argparse.ArgumentParser()
    argument.add_argument("--post", help="Sportsfilter Post ID")
    args = argument.parse_args()
    post = int(args.post) if args.post else 20820
    p = Parser("http://www.sportsfilter.com/news/%d" % post)
    # p = Parser("http://www.sportsfilter.com/news/20803/nfl-pick-em-week-3-indys-bad-luck-edition")
    # p = Parser("http://www.sportsfilter.com/news/20790/nfl-pick-em-week-2-teddy-bridgewater-fail")
    # p = Parser("http://www.sportsfilter.com/news/20769/nfl-pick-em-week-1-win-one-duke")
