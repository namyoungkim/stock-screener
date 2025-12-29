"""Discord bot main entry point."""

import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from bot.api import api_client

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")


class StockScreenerBot(discord.Client):
    """Stock Screener Discord Bot."""

    def __init__(self):
        intents = discord.Intents.default()
        # message_content intent는 슬래시 명령어에 불필요
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        """Set up the bot."""
        await self.tree.sync()

    async def on_ready(self):
        """Called when the bot is ready."""
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")


bot = StockScreenerBot()


def format_number(value: float | None) -> str:
    """Format number for display."""
    if value is None:
        return "-"
    return f"{value:,.2f}"


def format_percent(value: float | None) -> str:
    """Format percentage for display."""
    if value is None:
        return "-"
    return f"{value * 100:.2f}%"


def format_market_cap(value: float | None) -> str:
    """Format market cap for display."""
    if value is None:
        return "-"
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.2f}M"
    return f"${value:,.0f}"


@bot.tree.command(name="stock", description="Get stock information")
@app_commands.describe(
    ticker="Stock ticker symbol (e.g., AAPL, 005930)",
    market="Market (US, KOSPI, KOSDAQ)",
)
async def stock_command(
    interaction: discord.Interaction,
    ticker: str,
    market: str | None = None,
):
    """Get stock information."""
    await interaction.response.defer()

    try:
        data = await api_client.get_stock(ticker.upper(), market)
        company = data["company"]
        metrics = data.get("metrics", {})
        price = data.get("price", {})

        embed = discord.Embed(
            title=f"{company['ticker']} - {company['name']}",
            color=discord.Color.blue(),
        )

        # Market badge
        embed.add_field(
            name="Market",
            value=company["market"],
            inline=True,
        )

        if company.get("sector"):
            embed.add_field(
                name="Sector",
                value=company["sector"],
                inline=True,
            )

        # Price info
        if price:
            embed.add_field(
                name="Price",
                value=f"{price.get('close', '-')} {company['currency']}",
                inline=True,
            )
            embed.add_field(
                name="Market Cap",
                value=format_market_cap(price.get("market_cap")),
                inline=True,
            )

        # Metrics
        if metrics:
            metrics_text = (
                f"P/E: {format_number(metrics.get('pe_ratio'))}\n"
                f"P/B: {format_number(metrics.get('pb_ratio'))}\n"
                f"ROE: {format_percent(metrics.get('roe'))}\n"
                f"Div Yield: {format_percent(metrics.get('dividend_yield'))}"
            )
            embed.add_field(name="Key Metrics", value=metrics_text, inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")


@bot.tree.command(name="screen", description="Screen stocks with a preset strategy")
@app_commands.describe(
    preset="Preset strategy (graham, buffett, dividend, deep_value)",
    market="Market filter (US, KOSPI, KOSDAQ)",
    limit="Number of results (default: 10)",
)
@app_commands.choices(
    preset=[
        app_commands.Choice(name="Graham Classic", value="graham"),
        app_commands.Choice(name="Buffett Quality", value="buffett"),
        app_commands.Choice(name="Dividend Value", value="dividend"),
        app_commands.Choice(name="Deep Value", value="deep_value"),
    ]
)
async def screen_command(
    interaction: discord.Interaction,
    preset: str,
    market: str | None = None,
    limit: int = 10,
):
    """Screen stocks with a preset strategy."""
    await interaction.response.defer()

    try:
        data = await api_client.screen(
            preset=preset, market=market, limit=min(limit, 20)
        )

        embed = discord.Embed(
            title=f"Screening Results: {preset.replace('_', ' ').title()}",
            description=f"Found {data['total']} stocks",
            color=discord.Color.green(),
        )

        stocks = data["stocks"][:10]  # Limit to 10 for display

        if not stocks:
            embed.add_field(name="No Results", value="No stocks match the criteria.")
        else:
            # Create table-like display
            lines = []
            for stock in stocks:
                pe = format_number(stock.get("pe_ratio"))
                pb = format_number(stock.get("pb_ratio"))
                roe = format_percent(stock.get("roe"))
                lines.append(
                    f"**{stock['ticker']}** ({stock['market']}) - "
                    f"P/E: {pe}, P/B: {pb}, ROE: {roe}"
                )

            embed.add_field(
                name="Top Results",
                value="\n".join(lines),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")


@bot.tree.command(name="presets", description="List available preset strategies")
async def presets_command(interaction: discord.Interaction):
    """List available preset strategies."""
    await interaction.response.defer()

    try:
        presets = await api_client.get_presets()

        embed = discord.Embed(
            title="Available Preset Strategies",
            color=discord.Color.purple(),
        )

        for preset in presets:
            filters_text = ", ".join(
                f"{f['metric']} {f['operator']} {f['value']}" for f in preset["filters"]
            )
            embed.add_field(
                name=f"{preset['name']} (`{preset['id']}`)",
                value=f"{preset['description']}\n*Filters: {filters_text}*",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")


@bot.tree.command(name="search", description="Search stocks by name or ticker")
@app_commands.describe(
    query="Search query",
    market="Market filter (US, KOSPI, KOSDAQ)",
)
async def search_command(
    interaction: discord.Interaction,
    query: str,
    market: str | None = None,
):
    """Search stocks."""
    await interaction.response.defer()

    try:
        data = await api_client.get_stocks(search=query, market=market, limit=10)

        embed = discord.Embed(
            title=f"Search Results: {query}",
            description=f"Found {data['total']} stocks",
            color=discord.Color.blue(),
        )

        stocks = data["stocks"][:10]

        if not stocks:
            embed.add_field(name="No Results", value="No stocks found.")
        else:
            lines = []
            for stock in stocks:
                cap = format_market_cap(stock.get("market_cap"))
                lines.append(
                    f"**{stock['ticker']}** - {stock['name']} ({stock['market']}) - {cap}"
                )

            embed.add_field(
                name="Results",
                value="\n".join(lines),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")


# ============================================
# Watchlist Commands
# ============================================


@bot.tree.command(name="watch", description="Add a stock to your watchlist")
@app_commands.describe(
    ticker="Stock ticker symbol (e.g., AAPL, 005930)",
    market="Market (US, KOSPI, KOSDAQ)",
)
async def watch_command(
    interaction: discord.Interaction,
    ticker: str,
    market: str | None = None,
):
    """Add stock to watchlist."""
    await interaction.response.defer()

    try:
        discord_user_id = str(interaction.user.id)
        result = await api_client.add_to_watchlist(
            discord_user_id, ticker.upper(), market
        )

        embed = discord.Embed(
            title="Added to Watchlist",
            description=f"**{result['ticker']}** - {result['name']}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Market", value=result["market"], inline=True)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            await interaction.followup.send(f"Stock '{ticker.upper()}' not found.")
        elif "409" in error_msg:
            await interaction.followup.send(
                f"'{ticker.upper()}' is already in your watchlist."
            )
        else:
            await interaction.followup.send(f"Error: {e}")


@bot.tree.command(name="unwatch", description="Remove a stock from your watchlist")
@app_commands.describe(
    ticker="Stock ticker symbol to remove",
    market="Market (US, KOSPI, KOSDAQ)",
)
async def unwatch_command(
    interaction: discord.Interaction,
    ticker: str,
    market: str | None = None,
):
    """Remove stock from watchlist."""
    await interaction.response.defer()

    try:
        discord_user_id = str(interaction.user.id)
        await api_client.remove_from_watchlist(discord_user_id, ticker.upper(), market)

        embed = discord.Embed(
            title="Removed from Watchlist",
            description=f"**{ticker.upper()}** has been removed.",
            color=discord.Color.orange(),
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            await interaction.followup.send(
                f"'{ticker.upper()}' is not in your watchlist."
            )
        else:
            await interaction.followup.send(f"Error: {e}")


@bot.tree.command(name="watchlist", description="View your watchlist")
async def watchlist_command(interaction: discord.Interaction):
    """View user's watchlist."""
    await interaction.response.defer()

    try:
        discord_user_id = str(interaction.user.id)
        data = await api_client.get_watchlist(discord_user_id)

        embed = discord.Embed(
            title="Your Watchlist",
            description=f"Total: {data['total']} stocks",
            color=discord.Color.gold(),
        )

        items = data["items"][:15]  # Limit display

        if not items:
            embed.add_field(
                name="Empty",
                value="Your watchlist is empty. Use `/watch {ticker}` to add stocks.",
            )
        else:
            lines = []
            for item in items:
                lines.append(
                    f"**{item['ticker']}** - {item['name']} ({item['market']})"
                )

            embed.add_field(
                name="Stocks",
                value="\n".join(lines),
                inline=False,
            )

            if data["total"] > 15:
                embed.set_footer(text=f"Showing 15 of {data['total']} stocks")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")


# ============================================
# Alert Commands
# ============================================

# Supported metrics for alerts
ALERT_METRICS = [
    app_commands.Choice(name="P/E Ratio", value="pe_ratio"),
    app_commands.Choice(name="P/B Ratio", value="pb_ratio"),
    app_commands.Choice(name="ROE", value="roe"),
    app_commands.Choice(name="RSI", value="rsi"),
    app_commands.Choice(name="Dividend Yield", value="dividend_yield"),
    app_commands.Choice(name="Price", value="latest_price"),
    app_commands.Choice(name="Graham Number", value="graham_number"),
    app_commands.Choice(name="52W High", value="fifty_two_week_high"),
    app_commands.Choice(name="52W Low", value="fifty_two_week_low"),
]

ALERT_OPERATORS = [
    app_commands.Choice(name="< (less than)", value="<"),
    app_commands.Choice(name="<= (at most)", value="<="),
    app_commands.Choice(name="= (equals)", value="="),
    app_commands.Choice(name=">= (at least)", value=">="),
    app_commands.Choice(name="> (greater than)", value=">"),
]


@bot.tree.command(name="alert", description="Create a price/metric alert")
@app_commands.describe(
    ticker="Stock ticker symbol (e.g., AAPL, 005930)",
    metric="Metric to monitor",
    operator="Comparison operator",
    value="Target value",
    market="Market (US, KOSPI, KOSDAQ)",
)
@app_commands.choices(metric=ALERT_METRICS, operator=ALERT_OPERATORS)
async def alert_command(
    interaction: discord.Interaction,
    ticker: str,
    metric: str,
    operator: str,
    value: float,
    market: str | None = None,
):
    """Create a new alert."""
    await interaction.response.defer()

    try:
        discord_user_id = str(interaction.user.id)
        result = await api_client.create_alert(
            discord_user_id,
            ticker.upper(),
            metric,
            operator,
            value,
            market,
        )

        embed = discord.Embed(
            title="Alert Created",
            description=f"**{result['ticker']}** - {result['name']}",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Condition",
            value=f"{metric.replace('_', ' ').title()} {operator} {value}",
            inline=False,
        )
        embed.add_field(name="Market", value=result["market"], inline=True)
        embed.add_field(name="Status", value="Active", inline=True)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            await interaction.followup.send(f"Stock '{ticker.upper()}' not found.")
        elif "409" in error_msg:
            await interaction.followup.send("This alert condition already exists.")
        else:
            await interaction.followup.send(f"Error: {e}")


@bot.tree.command(name="alerts", description="View your alerts")
async def alerts_command(interaction: discord.Interaction):
    """View user's alerts."""
    await interaction.response.defer()

    try:
        discord_user_id = str(interaction.user.id)
        data = await api_client.get_alerts(discord_user_id)

        embed = discord.Embed(
            title="Your Alerts",
            description=f"Total: {data['total']} alerts",
            color=discord.Color.blue(),
        )

        items = data["items"][:10]  # Limit display

        if not items:
            embed.add_field(
                name="Empty",
                value="You have no alerts. Use `/alert` to create one.",
            )
        else:
            for item in items:
                status = "Active" if item["is_active"] else "Paused"
                condition = f"{item['metric'].replace('_', ' ').title()} {item['operator']} {item['value']}"
                embed.add_field(
                    name=f"{item['ticker']} ({item['market']})",
                    value=f"{condition}\nStatus: {status}\nID: `{item['id'][:8]}...`",
                    inline=True,
                )

            if data["total"] > 10:
                embed.set_footer(text=f"Showing 10 of {data['total']} alerts")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")


@bot.tree.command(name="delalert", description="Delete an alert")
@app_commands.describe(
    alert_id="Alert ID (use /alerts to see IDs)",
)
async def delalert_command(
    interaction: discord.Interaction,
    alert_id: str,
):
    """Delete an alert."""
    await interaction.response.defer()

    try:
        discord_user_id = str(interaction.user.id)
        await api_client.delete_alert(discord_user_id, alert_id)

        embed = discord.Embed(
            title="Alert Deleted",
            description=f"Alert `{alert_id[:8]}...` has been deleted.",
            color=discord.Color.orange(),
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            await interaction.followup.send("Alert not found.")
        else:
            await interaction.followup.send(f"Error: {e}")


@bot.tree.command(name="togglealert", description="Toggle an alert on/off")
@app_commands.describe(
    alert_id="Alert ID (use /alerts to see IDs)",
)
async def togglealert_command(
    interaction: discord.Interaction,
    alert_id: str,
):
    """Toggle alert active status."""
    await interaction.response.defer()

    try:
        discord_user_id = str(interaction.user.id)
        result = await api_client.toggle_alert(discord_user_id, alert_id)

        status = "Active" if result["is_active"] else "Paused"
        color = (
            discord.Color.green() if result["is_active"] else discord.Color.greyple()
        )

        embed = discord.Embed(
            title=f"Alert {status}",
            description=f"**{result['ticker']}** - {result['name']}",
            color=color,
        )
        condition = f"{result['metric'].replace('_', ' ').title()} {result['operator']} {result['value']}"
        embed.add_field(name="Condition", value=condition, inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            await interaction.followup.send("Alert not found.")
        else:
            await interaction.followup.send(f"Error: {e}")


def main():
    """Run the bot."""
    if not DISCORD_BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN not set")
        return

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
