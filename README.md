# NFL odds relay

Pulls NFL game lines and player props from every US sportsbook on
[The Odds API](https://the-odds-api.com) on game days and commits them to
`odds/`, where the `nfl-slate-research` Claude skill reads them. FanDuel is the quoted book; the
others give a consensus probability and the best available price.

Schedule: Sun, Mon, Thu at 6:45 AM Central. Run it by hand from the Actions tab with an optional
date.

Setup: add a repository secret named `ODDS_API_KEY`. The repo is public so cloud runs can read
the JSON without credentials; the key stays in Actions secrets and never appears in the files.

Credit use: The Odds API bills markets × regions, not per book, so pulling all US books costs the
same as one: 3 per pull for game lines plus 6 per game for props. That's roughly 430 a month for
Thu/Sun/Mon, under the free plan's 500. Adding a manual run costs 3 + 6 per game.
