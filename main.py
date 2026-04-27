import discord
from discord import app_commands, ui
import sqlite3
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
WORKER_CHANNEL_ID = 1497993985837498402 # Your specific Channel ID
ADMIN_ID = 930518448268804096          # Your specific User ID

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
            page_count INTEGER DEFAULT 0,
            worker_name TEXT,
            worker_id INTEGER,
            message_id INTEGER,
            status TEXT DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        cursor.execute('ALTER TABLE assignments ADD COLUMN page_count INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass 
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

# --- BOT A: INTAKE ---
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
            embed.add_field(name="Description", value=self.description.value, inline=False)
            embed.set_footer(text="React with 👍 to claim this job!")
            
            channel = interaction.guild.get_channel(WORKER_CHANNEL_ID)
            if channel:
                sent_msg = await channel.send(embed=embed)
                await sent_msg.add_reaction("👍")
                
                conn = sqlite3.connect('hostel_business.db')
                cursor = conn.cursor()
                cursor.execute('UPDATE assignments SET message_id = ? WHERE ticket_id = ?', (sent_msg.id, ticket_id))
                conn.commit()
                conn.close()
            
            await interaction.response.send_message(f"✅ Ticket **#{ticket_id}** created!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid price format.", ephemeral=True)

# --- BOT CLIENT ---
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

    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.user.id: return 
        if str(payload.emoji) == "👍":
            conn = sqlite3.connect('hostel_business.db')
            cursor = conn.cursor()
            cursor.execute('SELECT ticket_id, status FROM assignments WHERE message_id = ?', (payload.message_id,))
            result = cursor.fetchone()
            
            if result and result[1] == 'OPEN':
                cursor.execute('UPDATE assignments SET status = "CLAIMED", worker_id = ?, worker_name = ? WHERE ticket_id = ?', 
                               (payload.user_id, payload.member.name, result[0]))
                conn.commit()
                channel = self.get_channel(payload.channel_id)
                await channel.send(f"💼 **Ticket #{result[0]}** assigned to {payload.member.mention}!")
            conn.close()

bot = HostelBot()

# --- COMMANDS ---

@bot.tree.command(name="new_order", description="The Guy: Start a new assignment ticket")
async def new_order(interaction: discord.Interaction):
    await interaction.response.send_modal(IntakeForm())

@bot.tree.command(name="complete", description="The Guy: Mark as PAID and log pages")
@app_commands.describe(ticket_id="Ticket ID", pages="Number of pages written")
async def complete(interaction: discord.Interaction, ticket_id: int, pages: int):
    conn = sqlite3.connect('hostel_business.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status, message_id FROM assignments WHERE ticket_id = ?', (ticket_id,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return await interaction.response.send_message(f"❓ Ticket #{ticket_id} not found.", ephemeral=True)
    if result[0] == 'PAID':
        conn.close()
        return await interaction.response.send_message(f"✅ Ticket #{ticket_id} is already paid.", ephemeral=True)

    cursor.execute('UPDATE assignments SET status = "PAID", page_count = ? WHERE ticket_id = ?', (pages, ticket_id))
    conn.commit()
    conn.close()
    
    channel = interaction.guild.get_channel(WORKER_CHANNEL_ID)
    if channel and result[1]:
        try:
            msg = await channel.fetch_message(result[1])
            await msg.delete()
        except:
            pass
    await interaction.response.send_message(f"💰 Ticket #{ticket_id} closed. {pages} pages logged for Yahya.", ephemeral=True)

@bot.tree.command(name="payouts", description="Boss View: See Yahya's total earnings")
async def payouts(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("🚫 Unauthorized.", ephemeral=True)

    conn = sqlite3.connect('hostel_business.db')
    cursor = conn.cursor()
    
    # Calculate Yahya's commission (pages * 1)
    cursor.execute("SELECT SUM(page_count) FROM assignments WHERE status = 'PAID'")
    yahya_total = cursor.fetchone()[0] or 0

    # Get total revenue for context
    cursor.execute("SELECT SUM(total_price) FROM assignments WHERE status = 'PAID'")
    total_revenue = cursor.fetchone()[0] or 0
    
    # Get breakdown by worker
    cursor.execute("SELECT worker_name, SUM(page_count) FROM assignments WHERE status = 'PAID' GROUP BY worker_name")
    rows = cursor.fetchall()
    
    embed = discord.Embed(title="💰 Yahya's Commission Report", color=discord.Color.green())
    
    if not rows:
        embed.description = "No completed assignments yet."
    else:
        for row in rows:
            name, pages = row
            embed.add_field(
                name=f"Worker: {name}", 
                value=f"Wrote {pages} pages ➔ **₹{pages}** for Yahya", 
                inline=False
            )
    
    embed.add_field(name="──────────────", value=" ", inline=False)
    embed.add_field(name="📈 Total Money Handled", value=f"₹{total_revenue}", inline=True)
    embed.add_field(name="💵 YOUR TOTAL CUT", value=f"₹{yahya_total}", inline=True)
    
    await interaction.response.send_message(embed=embed)
    conn.close()

if __name__ == "__main__":
    bot.run(TOKEN)
