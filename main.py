import discord
from discord import app_commands, ui
import sqlite3
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
WORKER_CHANNEL_ID = 1234567890  # Replace with your actual Worker Channel ID
ADMIN_ID = 1234567890          # Replace with YOUR Discord User ID for security

# --- DATABASE LAYER ---
def init_db():
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
            worker_name TEXT,
            worker_id INTEGER,
            message_id INTEGER,
            status TEXT DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(client, sub, desc, dead, price):
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

def update_ticket_message(ticket_id, msg_id):
    conn = sqlite3.connect('hostel_business.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE assignments SET message_id = ? WHERE ticket_id = ?', (msg_id, ticket_id))
    conn.commit()
    conn.close()

# --- BOT A: THE CONCIERGE (INTAKE) ---
class IntakeForm(ui.Modal, title='Hostel Assignment Intake'):
    subject = ui.TextInput(label='Subject/Module', placeholder='e.g., Python, Engineering Math')
    description = ui.TextInput(label='Task Details', style=discord.TextStyle.paragraph, max_length=500)
    deadline = ui.TextInput(label='Deadline', placeholder='e.g., Tomorrow 5 PM')
    price = ui.TextInput(label='Total Price (₹)', placeholder='e.g., 500')

    async def on_submit(self, interaction: discord.Interaction):
        try:
            price_val = float(self.price.value)
            ticket_id = save_to_db(interaction.user.name, self.subject.value, self.description.value, self.deadline.value, price_val)

            embed = discord.Embed(title=f"🚨 New Job: Ticket #{ticket_id}", color=discord.Color.green())
            embed.add_field(name="Subject", value=self.subject.value, inline=False)
            embed.add_field(name="Deadline", value=self.deadline.value, inline=True)
            embed.add_field(name="Budget", value=f"₹{price_val}", inline=True)
            embed.set_footer(text="React with 👍 to claim this job!")

            channel = interaction.guild.get_channel(WORKER_CHANNEL_ID)
            if channel:
                sent_msg = await channel.send(embed=embed)
                await sent_msg.add_reaction("👍")
                update_ticket_message(ticket_id, sent_msg.id)
            
            await interaction.response.send_message(f"✅ Ticket **#{ticket_id}** created!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid price format.", ephemeral=True)

# --- THE BOT CLIENT ---
class HostelBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        init_db()
        print(f'Logged in as {self.user}')

    # --- BOT B: THE DISPATCHER (CLAIMING) ---
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.user.id: return # Ignore bot's own reaction

        if str(payload.emoji) == "👍":
            conn = sqlite3.connect('hostel_business.db')
            cursor = conn.cursor()
            cursor.execute('SELECT ticket_id, status FROM assignments WHERE message_id = ?', (payload.message_id,))
            result = cursor.fetchone()

            if result and result[1] == 'OPEN':
                ticket_id = result[0]
                cursor.execute('UPDATE assignments SET status = "CLAIMED", worker_id = ?, worker_name = ? WHERE ticket_id = ?', 
                               (payload.user_id, payload.member.name, ticket_id))
                conn.commit()
                
                channel = self.get_channel(payload.channel_id)
                await channel.send(f"💼 **Ticket #{ticket_id}** is now assigned to {payload.member.mention}!")
            conn.close()

bot = HostelBot()

# --- COMMANDS ---
@bot.tree.command(name="new_order", description="The Guy: Start a new assignment ticket")
async def new_order(interaction: discord.Interaction):
    await interaction.response.send_modal(IntakeForm())

# --- BOT C: THE TRACKER (EARNINGS) ---
@bot.tree.command(name="payouts", description="View financial records")
async def payouts(interaction: discord.Interaction):
    # Only the Admin (You) or the designated Guy should see this
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("🚫 Unauthorized.", ephemeral=True)

    conn = sqlite3.connect('hostel_business.db')
    cursor = conn.cursor()
    
    # Calculate simple commission (10% for you, 90% for them)
    cursor.execute("SELECT worker_name, SUM(total_price) FROM assignments WHERE status = 'CLAIMED' GROUP BY worker_name")
    rows = cursor.fetchall()
    
    embed = discord.Embed(title="📊 Payout Summary (Work in Progress)", color=discord.Color.gold())
    total_revenue = 0
    
    for row in rows:
        name, amount = row
        total_revenue += amount
        embed.add_field(name=name, value=f"Earned: ₹{amount * 0.9} (to pay)", inline=False)
    
    embed.set_footer(text=f"Total System Revenue: ₹{total_revenue} | Your Cut: ₹{total_revenue * 0.1}")
    await interaction.response.send_message(embed=embed)
    conn.close()

if __name__ == "__main__":
    bot.run(TOKEN)
