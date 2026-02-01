# display.py
"""CLI output formatting and display functions."""

from tabulate import tabulate
from config import NEGATIVE_CATEGORIES


# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def color_text(text, color):
    """Wrap text in color codes."""
    return f"{color}{text}{Colors.END}"


def format_rank(rank, total_teams=10):
    """Color-code a rank value."""
    if not isinstance(rank, int):
        return str(rank)

    if rank <= 3:
        return color_text(f"#{rank}", Colors.GREEN)
    elif rank >= total_teams - 2:
        return color_text(f"#{rank}", Colors.RED)
    else:
        return f"#{rank}"


def format_value(value, category):
    """Format a stat value appropriately."""
    if value is None or value == '-':
        return '-'

    try:
        val = float(value)
        if category in ['FG%', 'FT%']:
            return f"{val:.3f}"
        elif category in ['PTS', 'REB', 'AST', '3PTM', 'ST', 'BLK', 'TO', 'DD']:
            return f"{val:.1f}"
        else:
            return f"{val:.2f}"
    except (ValueError, TypeError):
        return str(value)


def display_header(title):
    """Display a section header."""
    print("\n" + "=" * 60)
    print(color_text(f" {title}", Colors.BOLD))
    print("=" * 60)


def display_standings(standings_data):
    """Display league standings table."""
    display_header("League Standings")

    headers = ['Rank', 'Team', 'W', 'L', 'T']
    rows = []

    for team in standings_data:
        rows.append([
            team['rank'],
            team['name'][:25],
            team['wins'],
            team['losses'],
            team['ties']
        ])

    print(tabulate(rows, headers=headers, tablefmt='simple'))


def display_category_rankings(rankings, team_name="Your Team"):
    """Display team's ranking in each category."""
    display_header(f"Category Rankings - {team_name}")

    headers = ['Category', 'Value', 'Rank', 'Status']
    rows = []

    for cat, data in rankings.items():
        rank = data.get('rank', '-')
        value = format_value(data.get('value'), cat)
        total = data.get('total_teams', 10)

        if isinstance(rank, int):
            if rank <= 3:
                status = color_text("STRENGTH", Colors.GREEN)
            elif rank >= total - 2:
                status = color_text("WEAKNESS", Colors.RED)
            else:
                status = "Average"
            rank_str = format_rank(rank, total)
        else:
            status = "-"
            rank_str = str(rank)

        rows.append([cat, value, rank_str, status])

    print(tabulate(rows, headers=headers, tablefmt='simple'))


def display_strengths_weaknesses(strengths, weaknesses):
    """Display team strengths and weaknesses summary."""
    display_header("Team Analysis Summary")

    print(color_text("\n STRENGTHS (Top 3):", Colors.GREEN))
    if strengths:
        for s in strengths:
            print(f"  • {s['category']}: Rank #{s['rank']} ({format_value(s['value'], s['category'])})")
    else:
        print("  No clear strengths identified")

    print(color_text("\n WEAKNESSES (Bottom 3):", Colors.RED))
    if weaknesses:
        for w in weaknesses:
            print(f"  • {w['category']}: Rank #{w['rank']} ({format_value(w['value'], w['category'])})")
    else:
        print("  No clear weaknesses identified")


def display_league_comparison(comparison):
    """Display comparison of team stats to league average."""
    display_header("Comparison to League Average")

    headers = ['Category', 'Your Team', 'League Avg', 'Diff', 'vs Avg']
    rows = []

    for cat, data in comparison.items():
        team_val = format_value(data['team_value'], cat)
        league_avg = format_value(data['league_avg'], cat)
        diff = data['difference']
        diff_pct = data['diff_percent']

        if data['is_better']:
            indicator = color_text(f"+{diff_pct:.1f}%", Colors.GREEN)
        else:
            indicator = color_text(f"{diff_pct:.1f}%", Colors.RED)

        rows.append([cat, team_val, league_avg, format_value(diff, cat), indicator])

    print(tabulate(rows, headers=headers, tablefmt='simple'))


def display_roster(roster_analysis, categories):
    """Display roster with player stats."""
    display_header("Roster Analysis")

    # Show subset of important categories
    display_cats = categories[:8] if len(categories) > 8 else categories
    headers = ['Player', 'Pos'] + display_cats

    rows = []
    for player in roster_analysis:
        row = [
            player['name'][:20],
            player['position']
        ]
        for cat in display_cats:
            row.append(format_value(player['stats'].get(cat, 0), cat))
        rows.append(row)

    print(tabulate(rows, headers=headers, tablefmt='simple'))


def display_free_agent_recommendations(pickups, weaknesses):
    """Display free agent pickup recommendations."""
    display_header("Free Agent Recommendations")

    # Show which weaknesses we're targeting
    if weaknesses:
        print(color_text("\nTargeting weaknesses:", Colors.YELLOW))
        for w in weaknesses:
            print(f"  • {w['category']} (Rank #{w['rank']})")

    print("\n" + color_text("Top Pickup Candidates:", Colors.BLUE))

    if not pickups:
        print("  No recommendations available")
        return

    headers = ['Rank', 'Player', 'Positions', 'Score', 'Key Stats']
    rows = []

    for i, pickup in enumerate(pickups, 1):
        stats = pickup.get('stats', {})
        # Show top 3 stats
        stat_strs = []
        for cat in ['PTS', 'REB', 'AST', '3PTM', 'ST', 'BLK']:
            if cat in stats:
                val = stats[cat]
                if val and float(val) > 0:
                    stat_strs.append(f"{cat}:{format_value(val, cat)}")
        key_stats = ', '.join(stat_strs[:4])

        positions = ','.join(pickup.get('positions', [])[:3])

        rows.append([
            i,
            pickup['name'][:25],
            positions,
            f"{pickup['score']:.1f}",
            key_stats
        ])

    print(tabulate(rows, headers=headers, tablefmt='simple'))


def display_drop_recommendations(drops):
    """Display drop candidate recommendations."""
    display_header("Drop Candidates")

    if not drops:
        print("  No drop recommendations")
        return

    print(color_text("\nPlayers contributing least to your weak categories:", Colors.YELLOW))

    headers = ['Player', 'Pos', 'Weakness Contrib', 'Strength Contrib']
    rows = []

    for drop in drops[:5]:
        rows.append([
            drop['name'][:25],
            drop['position'],
            f"{drop['weakness_contribution']:.1f}",
            f"{drop['strength_contribution']:.1f}"
        ])

    print(tabulate(rows, headers=headers, tablefmt='simple'))


def display_pickup_suggestions(suggestions):
    """Display combined pickup and drop suggestions."""
    display_free_agent_recommendations(
        suggestions['pickups'],
        suggestions['weaknesses']
    )
    print()
    display_drop_recommendations(suggestions['drops'])


def display_category_leaders(category, free_agents):
    """Display top free agents for a specific category."""
    display_header(f"Top Free Agents - {category}")

    if not free_agents:
        print(f"  No free agents found for {category}")
        return

    headers = ['Rank', 'Player', 'Positions', category]
    rows = []

    for i, fa in enumerate(free_agents, 1):
        positions = ','.join(fa.get('positions', [])[:3])
        rows.append([
            i,
            fa['name'][:25],
            positions,
            format_value(fa['value'], category)
        ])

    print(tabulate(rows, headers=headers, tablefmt='simple'))


def display_menu():
    """Display the main menu."""
    print("\n" + "=" * 40)
    print(color_text(" Yahoo Fantasy Basketball Analyzer", Colors.BOLD))
    print("=" * 40)
    print("""
1. View my team's category analysis
2. Compare my team to the league
3. View league standings
4. View category rankings (all teams)
5. Get free agent recommendations
6. Get pickup/drop suggestions
7. Browse free agents by category
8. Exit
""")


def display_error(message):
    """Display an error message."""
    print(color_text(f"\n Error: {message}", Colors.RED))


def display_success(message):
    """Display a success message."""
    print(color_text(f"\n {message}", Colors.GREEN))


def display_info(message):
    """Display an info message."""
    print(color_text(f"\n {message}", Colors.BLUE))
