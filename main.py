import discord
from discord import app_commands, ui
import sqlite3
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
WORKER_CHANNEL_ID = 1234567890  # Replace with actual Worker Channel ID
ADMIN_ID = 1234567890           # Replace with YOUR Discord User ID

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
            embed.add_field(name="Description", value=self.description.value, inline=False)
            embed.set_footer(text="React with 👍 to claim this job!")

            channel = interaction.guild.get_channel(WORKER_CHANNEL_ID)
            if channel:
                sent_msg = await channel.send(embed=embed)
                await sent_msg.add_reaction("👍")
                
                # Update DB with message ID for Bot B and C to reference
                conn = sqlite3.connect('hostel_business.db')
                cursor = conn.cursor()
                cursor.execute('UPDATE assignments SET message_id = ? WHERE ticket_id = ?', (sent_msg.id, ticket_id))
                conn.commit()
                conn.close()
            
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
        if payload.user_id == self.user.id: return 

        if str(payload.emoji) == "👍":
            conn = sqlite3.connect('hostel_business.db')
            cursor = conn.cursor()
            cursor.execute('SELECT ticket_id, status FROM assignments WHERE message_id = ?', (payload.message_id,))
            result = cursor.fetchone()

            if result:
                ticket_id, status = result
                # Race condition check: Only claim if it's still OPEN
                if status == 'OPEN':
                    cursor.execute('''
                        UPDATE assignments 
                        SET status = "CLAIMED", worker_id = ?, worker_name = ? 
                        WHERE ticket_id = ?
                    ''', (payload.user_id, payload.member.name, ticket_id))
                    conn.commit()
                    
                    channel = self.get_channel(payload.channel_id)
                    await channel.send(f"💼 **Ticket #{ticket_id}** assigned to {payload.member.mention}!")
                
            conn.close()

bot = HostelBot()

# --- BOT C: COMMANDS & TRACKING ---

@bot.tree.command(name="new_order", description="The Guy: Start a new assignment ticket")
async def new_order(interaction: discord.Interaction):
    await interaction.response.send_modal(IntakeForm())

@bot.tree.command(name="complete", description="The Guy: Mark ticket as paid and clean channel")
@app_commands.describe(ticket_id="The ID of the ticket to close")
async def complete(interaction: discord.Interaction, ticket_id: int):
    conn = sqlite3.connect('hostel_business.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT status, message_id FROM assignments WHERE ticket_id = ?', (ticket_id,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return await interaction.response.send_message(f"❓ Ticket #{ticket_id} not found.", ephemeral=True)
    
    status, msg_id = result
    if status == 'PAID':
        conn.close()
        return await interaction.response.send_message(f"✅ Ticket #{ticket_id} is already paid.", ephemeral=True)

    # 1. Update Database
    cursor.execute('UPDATE assignments SET status = "PAID" WHERE ticket_id = ?', (ticket_id,))
    conn.commit()
    conn.close()
    
    # 2. Delete Message from Worker Channel (Cleanup)
    cleanup_note = ""
    channel = interaction.guild.get_channel(WORKER_CHANNEL_ID)
    if channel and msg_id:
        try:
            msg_to_delete = await channel.fetch_message(msg_id)
            await msg_to_delete.delete()
            cleanup_note = "and channel cleared."
        except:
            cleanup_note = "(Job message was already manually deleted or not found)."

    await interaction.response.send_message(f"💰 Ticket #{ticket_id} marked as PAID {cleanup_note}", ephemeral=True)

@bot.tree.command(name="payouts", description="CFO View: View total earnings and splits")
async def payouts(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("🚫 Unauthorized.", ephemeral=True)

    conn = sqlite3.connect('hostel_business.db')
    cursor = conn.cursor()
    cursor.execute("SELECT worker_name, SUM(total_price) FROM assignments WHERE status = 'PAID' GROUP BY worker_name")
    rows = cursor.fetchall()
    
    embed = discord.Embed(title="📊 Financial Summary (PAID Jobs Only)", color=discord.Color.gold())
    total_revenue = 0
    
    if not rows:
        embed.description = "No completed payments found."
    else:
        for row in rows:
            name, total = row
            total_revenue += total
            worker_cut = total * 0.9
            embed.add_field(name=f"Worker: {name}", value=f"Revenue: ₹{total}\n**Pay Worker: ₹{worker_cut}**", inline=False)
    
    your_cut = total_revenue * 0.1
    embed.set_footer(text=f"Total Rev: ₹{total_revenue} | Your 10%: ₹{your_cut}")
    
    await interaction.response.send_message(embed=embed)
    conn.close()

if __name__ == "__main__":
    bot.run(TOKEN)
