import discord
from discord import app_commands, ui
import sqlite3
import datetime

# --- SETTINGS ---
TOKEN = 'YOUR_BOT_TOKEN_HERE'
WORKER_CHANNEL_ID = 1234567890  # The ID of the channel where Workers see jobs

# --- DATABASE LOGIC ---
def init_db():
    """Initializes the SQLite database and tables."""
    conn = sqlite3.connect('hostel_business.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT,
            deadline TEXT,
            total_price REAL,
            status TEXT DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(client, sub, desc, dead, price):
    """Saves a new order and returns the unique Ticket ID."""
    conn = sqlite3.connect('hostel_business.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO assignments (client_name, subject, description, deadline, total_price)
        VALUES (?, ?, ?, ?, ?)
    ''', (client, sub, desc, dead, price))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

# --- THE FORM (MODAL) ---
class IntakeForm(ui.Modal, title='Hostel Assignment Intake'):
    # Form Fields
    subject = ui.TextInput(label='Subject/Module', placeholder='e.g., Python Programming, Calculus...')
    description = ui.TextInput(label='Task Details', style=discord.TextStyle.paragraph, 
                               placeholder='Be specific: Page numbers, code requirements, etc.', max_length=500)
    deadline = ui.TextInput(label='Deadline', placeholder='e.g., Tuesday at 4 PM')
    price = ui.TextInput(label='Agreed Price (₹)', placeholder='e.g., 500')

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 1. Save to Database
            ticket_id = save_to_db(
                interaction.user.name, 
                self.subject.value, 
                self.description.value, 
                self.deadline.value, 
                float(self.price.value)
            )

            # 2. Create an Embed for the Workers Channel
            embed = discord.Embed(title=f"🚨 New Job: Ticket #{ticket_id}", color=discord.Color.green())
            embed.add_field(name="Subject", value=self.subject.value, inline=False)
            embed.add_field(name="Deadline", value=self.deadline.value, inline=True)
            embed.add_field(name="Budget", value=f"₹{self.price.value}", inline=True)
            embed.add_field(name="Description", value=self.description.value, inline=False)
            embed.set_footer(text=f"Client: {interaction.user.name}")

            # 3. Send to Worker Channel (Bot B will eventually handle the 'Claim' logic here)
            channel = interaction.guild.get_channel(WORKER_CHANNEL_ID)
            if channel:
                await channel.send(embed=embed)
            
            await interaction.response.send_message(f"✅ Order Logged! Ticket ID: **#{ticket_id}**. Workers have been notified.", ephemeral=True)
        
        except ValueError:
            await interaction.response.send_message("❌ Error: Please enter a valid number for the price.", ephemeral=True)

# --- BOT SETUP ---
class BotA(discord.Client):
    def __init__(self):
        # Intents allow the bot to see members and messages
        intents = discord.Intents.default()
        intents.members = True 
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Syncs the /commands with Discord
        await self.tree.sync()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        init_db() # Ensure DB is ready when bot starts
        print("------")

client = BotA()

@client.tree.command(name="new_order", description="The Guy: Start a new assignment ticket")
async def new_order(interaction: discord.Interaction):
    """The trigger command to open the intake form."""
    await interaction.response.send_modal(IntakeForm())

if __name__ == "__main__":
    client.run(TOKEN)
