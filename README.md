# spofi
Parser for Sportsfilter NFL Pick 'Em posts. 

Install by creating a [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/) 
(or use your native Python install) and running `pip install -r requirements.txt` from the root.

Right now the page URLs are hard-coded in the bottom of the command, need to update it to accept
command-line arguments. Run with `python nflparser.py` to see an example of behavior. To run with
a specific post, run `python nflparser.py --post=X` where `X` is the numerical post ID from a pool
URL at SportsFilter.
