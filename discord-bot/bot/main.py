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
        intents.message_content = True
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


def main():
    """Run the bot."""
    if not DISCORD_BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN not set")
        return

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
