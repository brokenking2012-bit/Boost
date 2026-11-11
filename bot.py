import discord
from discord.ext import commands , tasks
from PIL import Image, ImageDraw
import asyncio
import json
import os
import random
import re
import datetime
import io


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.invites = True

bot = commands.Bot(command_prefix='!', intents=intents)

# =================== EMOJI-SAFE HELPER FUNCTIONS ====================

def has_middleman_or_above(member: discord.Member):
    if member.guild_permissions.administrator:
        return True
    allowed_keywords = [
        "middleman", "servicer", "game manager", "sea mangaer", 
        "moderator", "sos", "administrator", "adminstrator", 
        "youtuber", "team lead", "co owner", "owner", "founder", "gamersberg manager"
    ]
    return any(any(keyword in role.name.lower() for keyword in allowed_keywords) for role in member.roles)

def has_moderator_or_above(member: discord.Member):
    if member.guild_permissions.administrator:
        return True
    allowed_keywords = [
        "moderator", "sos", "administrator", "adminstrator", 
        "youtuber", "team lead", "co owner", "owner", "founder", "gamersberg manager"
    ]
    return any(any(keyword in role.name.lower() for keyword in allowed_keywords) for role in member.roles)

async def check_hierarchy(ctx, target: discord.Member):
    if ctx.author.id == ctx.guild.owner_id:
        return True
    if ctx.author.top_role.position <= target.top_role.position:
        await ctx.send(f"❌ **Hierarchy Error:** You cannot perform this action on {target.mention} because their role is equal to or higher than yours!")
        return False
    return True


# ==================== SCAM, REGAIN ACCESS & EXPLANATION CLASSES ====================

class RegainAccessView(discord.ui.View):
    def __init__(self, target_member: discord.Member = None):
        super().__init__(timeout=None)
        self.target_member = target_member

    @discord.ui.button(label="Regain Access", style=discord.ButtonStyle.blurple, custom_id="regain_access_btn_strict")
    async def regain_access(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_middleman_or_above(interaction.user):
            await interaction.response.send_message("❌ Only a Middleman or higher staff can click this button!", ephemeral=True)
            return

        target = self.target_member
        if not target and interaction.message.mentions:
            target = interaction.message.mentions[0]

        if not target:
            await interaction.response.send_message("❌ Could not determine target user.", ephemeral=True)
            return

        role = discord.utils.find(lambda r: "verified trader" in r.name.lower(), interaction.guild.roles)
        if not role:
            await interaction.response.send_message("❌ Error: 'verified trader' role not found.", ephemeral=True)
            return

        try:
            await target.add_roles(role)
            await interaction.response.send_message(f"✅ Success! {target.mention} received the client role.", ephemeral=False)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to assign role: {e}", ephemeral=True)

class InitialScamView(discord.ui.View):
    def __init__(self, target_member: discord.Member = None):
        super().__init__(timeout=None)
        self.target_member = target_member

    @discord.ui.button(label="Yes ( I wish to scam )", style=discord.ButtonStyle.green, custom_id="yes_scam_btn_strict")
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        target = self.target_member
        if not target and interaction.message.mentions:
            target = interaction.message.mentions[0]

        view = RegainAccessView(target)
        await interaction.response.send_message(f"⚠️ {target.mention if target else 'User'} selected Yes. Middleman can grant access below:", view=view, ephemeral=False)

    @discord.ui.button(label="No ( i ready to get banned)", style=discord.ButtonStyle.red, custom_id="no_ban_btn_strict")
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        target = self.target_member
        if not target and interaction.message.mentions:
            target = interaction.message.mentions[0]
        if not target:
            await interaction.response.send_message("❌ Target not found.", ephemeral=True)
            return
        try:
            await interaction.guild.ban(target, reason="Chose to get banned via !comp prompt")
            await interaction.response.send_message(f"🔨 {target.mention} has been banned.", ephemeral=False)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to ban: {e}", ephemeral=True)

class MMExplanationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Understood", style=discord.ButtonStyle.green, custom_id="mm_understood_btn_strict")
    async def understood_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"✅ **{interaction.user.mention}** has confirmed understanding of the Middleman rules!", ephemeral=False)

    @discord.ui.button(label="Not understood", style=discord.ButtonStyle.red, custom_id="mm_not_understood_btn_strict")
    async def not_understood_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"❌ **{interaction.user.mention}** needs further assistance from a Middleman.", ephemeral=False)


# ==================== BOT EVENTS ====================

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}!')
    
    # Load all persistent views so buttons never break
    bot.add_view(RegainAccessView())
    bot.add_view(InitialScamView())
    bot.add_view(MMExplanationView())
    bot.add_view(MMTicketControlView())
    bot.add_view(MMOpenView())
    bot.add_view(SupportOpenView())
    bot.add_view(SupportTicketControlView())
    bot.add_view(WalletView())
    bot.add_view(RedeemView())
    
    print(f"✅ All views loaded successfully! Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

@bot.event
async def on_member_join(member):
    guild = member.guild

    # 1. Auto-assign "Gamersberg Family" role
    role = discord.utils.find(lambda r: "gamersberg family" in r.name.lower(), guild.roles)
    if role:
        try:
            await member.add_roles(role, reason="Automatic join role")
            print(f"✅ Assigned ' Family' role to {member.name}")
        except Exception as e:
            print(f"❌ Failed to assign auto-role: {e}")
    else:
        print("⚠️ Warning: Role ' Family' not found!")

    # 2. Track invites for +1 GB Coin
    try:
        old_invites = invite_cache.get(guild.id, [])
        new_invites = await guild.invites()
        invite_cache[guild.id] = new_invites

        for new_inv in new_invites:
            for old_inv in old_invites:
                if new_inv.code == old_inv.code and new_inv.uses > old_inv.uses:
                    inviter = new_inv.inviter
                    if inviter and not inviter.bot:
                        data = load_wallets()
                        uid = str(inviter.id)
                        data[uid] = data.get(uid, 0) + 1
                        save_wallets(data)
                        print(f"🪙 Added +1 coin to {inviter.name} for inviting {member.name}")
                    return
    except Exception as e:
        print(f"Invite tracking error: {e}")
            
    


# ==================== MIDDLEMAN & STAFF COMMANDS ====================

@bot.command(name="transfer")
async def transfer(ctx, new_middleman: discord.Member):
    if not has_middleman_or_above(ctx.author):
        await ctx.send("❌ You do not have permission to use this command.")
        return
    if "mm-" not in ctx.channel.name:
        await ctx.send("❌ This command can only be used inside a Middleman ticket channel.")
        return
    mm_role = discord.utils.find(lambda r: "middleman" in r.name.lower(), ctx.guild.roles)
    if mm_role:
        await ctx.channel.set_permissions(new_middleman, read_messages=True, send_messages=True)
    await ctx.send(f"🔄 Ticket transferred/shared with {new_middleman.mention} by {ctx.author.mention}.")

@bot.command(name="unclaim")
async def unclaim(ctx):
    if not has_middleman_or_above(ctx.author):
        await ctx.send("❌ You do not have permission to use this command.")
        return
    if "mm-" not in ctx.channel.name:
        await ctx.send("❌ This can only be used in a Middleman ticket.")
        return
    mm_role = discord.utils.find(lambda r: "middleman" in r.name.lower(), ctx.guild.roles)
    if mm_role:
        await ctx.channel.set_permissions(mm_role, read_messages=True, send_messages=True)
    await ctx.channel.set_permissions(ctx.author, read_messages=False)
    await ctx.send(f"🔓 Ticket unclaimed by {ctx.author.mention}. Reopened for other Middlemen.")

@bot.command(name='comp')
async def comp(ctx, member: discord.Member = None):
    if not has_middleman_or_above(ctx.author):
        await ctx.send("❌ You do not have permission to use this command.")
        return
    target = member or ctx.author
    message_text = "🚨 **UR SCAMMED** 🚨\n\nIf u wish to gain 10x more then tap the yes button or decilne the offer click no then u can stay banned, select your choice below:"
    view = InitialScamView(target)
    await ctx.send(content=message_text, view=view)

@bot.command(name='explainmm')
async def explainmm(ctx):
    if not has_middleman_or_above(ctx.author):
        await ctx.send("❌ You do not have permission to use this command.")
        return
    
    embed = discord.Embed(
        title="🛡️ Official BLOX HUB Middleman Guidelines & Rules",
        description=(
            "Our middleman service operates under strict guidelines to guarantee absolute trade security. "
            "Please read the old chat history and guidelines carefully before proceeding.\n\n"
            "**📋 Key Service Procedures:**\n"
            "• **Official Channels Only:** All trades must take place exclusively within official ticket channels. Always verify that your middleman holds the correct official role color.\n"
            "• **No Early Handover:** Never hand over any accounts, items, or login details until the middleman gives explicit approval.\n"
            "• **The Process:** The middleman holds the item from the seller, confirms the payment/trade terms from the buyer, and safely distributes everything to complete the transaction.\n"
            "• **Agreed Terms:** Both participants must agree on exact trade terms beforehand. Troll tickets or time-wasting will lead to strict consequences.\n\n"
            "👇 Click below to confirm your understanding of these instructions:"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="👑 BLOX HUB secure Trading • Safe & Trusted")
    view = MMExplanationView()
    await ctx.send(embed=embed, view=view)


# ==================== HIERARCHY-BASED MODERATION COMMANDS ====================

@bot.command(name="mute")
async def mute(ctx, member: discord.Member, *, reason="No reason provided"):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need the **Moderator** role or higher to mute users.")
        return
    if not await check_hierarchy(ctx, member):
        return
    muted_role = discord.utils.find(lambda r: "muted" in r.name.lower(), ctx.guild.roles)
    if not muted_role:
        await ctx.send("❌ Error: 'Muted' role not found in server.")
        return
    await member.add_roles(muted_role, reason=reason)
    await ctx.send(f"🔇 {member.mention} has been muted by {ctx.author.mention}.")

@bot.command(name="unmute")
async def unmute(ctx, member: discord.Member):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need the **Moderator** role or higher to unmute users.")
        return
    if not await check_hierarchy(ctx, member):
        return
    muted_role = discord.utils.find(lambda r: "muted" in r.name.lower(), ctx.guild.roles)
    if muted_role:
        await member.remove_roles(muted_role)
        await ctx.send(f"🔊 {member.mention} has been unmuted.")

@bot.command(name="kick")
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need the **Moderator** role or higher to kick users.")
        return
    if not await check_hierarchy(ctx, member):
        return
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member.mention} has been kicked by {ctx.author.mention}.")

@bot.command(name="ban")
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need the **Moderator** role or higher to ban users.")
        return
    if not await check_hierarchy(ctx, member):
        return
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member.mention} has been banned by {ctx.author.mention}.")

@bot.command(name="promo")
async def promo(ctx, member: discord.Member, *, role_name: str):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need staff permissions to promote.")
        return
    if not await check_hierarchy(ctx, member):
        return
    role = discord.utils.find(lambda r: role_name.lower() in r.name.lower(), ctx.guild.roles)
    if not role:
        await ctx.send(f"❌ Role matching '{role_name}' not found.")
        return
    await member.add_roles(role)
    await ctx.send(f"📈 {member.mention} was promoted with role **{role.name}**.")

@bot.command(name="demo")
async def demo(ctx, member: discord.Member, *, role_name: str):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need staff permissions to demote.")
        return
    if not await check_hierarchy(ctx, member):
        return
    role = discord.utils.find(lambda r: role_name.lower() in r.name.lower(), ctx.guild.roles)
    if not role:
        await ctx.send(f"❌ Role matching '{role_name}' not found.")
        return
    await member.remove_roles(role)
    await ctx.send(f"📉 {member.mention} was demoted (removed role **{role.name}**).")


# ==================== MIDDLEMAN TICKET SYSTEM CLASSES ====================

class MMRequestModal(discord.ui.Modal, title="morning market middleman Details"):
    giving = discord.ui.TextInput(
        label="What are YOU giving?",
        placeholder="e.g., Dragon Fruit, Kitsune",
        style=discord.TextStyle.short,
        required=True
    )
    receiving = discord.ui.TextInput(
        label="What are you RECEIVING?",
        placeholder="e.g., Gamepass, Leopard, Robux",
        style=discord.TextStyle.short,
        required=True
    )

    def __init__(self, partner: discord.Member):
        super().__init__()
        self.partner = partner

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔄 Creating your middleman ticket, please wait...", ephemeral=True)
        
        try:
            guild = interaction.guild
            mm_role = discord.utils.find(lambda r: "middleman" in r.name.lower(), guild.roles)
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                self.partner: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }



            if mm_role:
                overwrites[mm_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            channel_name = f"mm-{interaction.user.name}-{self.partner.name}".lower()[:30]
            
            # Retrieve category configuration safely
            config = load_config().get(str(guild.id), {})
            category_id = config.get("ticket_category_id")
            ticket_category = guild.get_channel(category_id) if category_id else None

            # Create channel under category if set
            ticket_channel = await guild.create_text_channel(
                name=channel_name, 
                overwrites=overwrites,
                category=ticket_category
            )

            

            embed = discord.Embed(
                title="🎟️ MIDDLEMAN TICKET CREATED",
                description=(
                    "• Your ticket is now live and waiting for a middleman to claim it.\n"
                    "• Do not spam ping any middleman.\n"
                    "• To use our service you must follow all server terms.\n"
                    "• Tickets are watched by support staff; any troll or time-wasting will lead to strict consequences."
                ),
                color=discord.Color.blue()
            )
            embed.add_field(name="🌐 Trading Partner", value=self.partner.mention, inline=False)
            embed.add_field(name=f"📦 {interaction.user.display_name}'s Side (Giving):", value=self.giving.value, inline=False)
            embed.add_field(name="🎁 Receiving Side:", value=self.receiving.value, inline=False)
            embed.set_footer(text="👑 BLOX HUB • Safe & Trusted")

            await ticket_channel.send(
                content=f"{interaction.user.mention} {self.partner.mention} {mm_role.mention if mm_role else ''}",
                embed=embed,
                view=MMTicketControlView()
            )

            await interaction.edit_original_response(content=f"✅ Your Middleman ticket has been created: {ticket_channel.mention}")

        except discord.Forbidden:
            await interaction.edit_original_response(content="❌ **Error:** I don't have permission to create channels! Give my bot role **Manage Channels**.")
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ An error occurred: `{e}`")

class PartnerSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="🔍 Type and select your trading partner from the server...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        partner = self.values[0]
        if partner == interaction.user:
            await interaction.response.send_message("❌ You cannot trade with yourself!", ephemeral=True)
            return
        if partner.bot:
            await interaction.response.send_message("❌ You cannot select a bot as a trading partner!", ephemeral=True)
            return
        
        await interaction.response.send_modal(MMRequestModal(partner=partner))

class PartnerSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(PartnerSelect())

class MMTicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="mm_claim_btn_v8")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_middleman_or_above(interaction.user):
            await interaction.response.send_message("❌ Only members with the **Middleman** role or higher can claim this ticket.", ephemeral=True)
            return

        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        
        await interaction.response.edit_message(view=self)

        guild = interaction.guild
        mm_role = discord.utils.find(lambda r: "middleman" in r.name.lower(), guild.roles)
        if mm_role:
            await interaction.channel.set_permissions(mm_role, read_messages=False)
        
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await interaction.channel.send(f"🔒 Claimed by {interaction.user.mention}! Other Middlemen no longer have access to this ticket.")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="mm_close_btn_v8")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_middleman_or_above(interaction.user):
            await interaction.response.send_message("❌ Only Middlemen or higher staff can close this ticket.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Saving trade log and closing ticket...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

class MMOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Middleman", style=discord.ButtonStyle.primary, emoji="🤝", custom_id="open_mm_select_btn_v7")
    async def open_select(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PartnerSelectView()
        await interaction.response.send_message("👇 Use the search menu below to select your trading partner:", view=view, ephemeral=True)

@bot.command(name="mmpanel")
@commands.has_permissions(administrator=True)
async def mmpanel(ctx):
    # 1. Grab the attachment URL if the user uploaded an image, gif, or video
    attachment_url = ctx.message.attachments[0].url if ctx.message.attachments else None

    embed = discord.Embed(
        title="🔒 BLOX HUB | MIDDLEMAN SERVICE",
        description=(
            "🔸 To request a middleman from this server, click the blue **\"Request Middleman\"** button on this message.\n\n"
            "🤝 **How does middleman work?**\n"
            "🔸 *Example: Trade is Dragon Fruit for Robux.*\n"
            "1. Seller gives Dragon Fruit to Middleman.\n"
            "2. Buyer pays seller Robux (After middleman confirms receiving item).\n"
            "3. Middleman gives buyer Dragon Fruit (After seller confirms receiving payment).\n\n"
            "🔒 **NOTES:**\n"
            "1. You must both agree on the deal before using a middleman. **Troll tickets will have consequences.**\n"
            "2. Specify what you're trading clearly (e.g., *Dragon Fruit in Blox Fruits > $20 Gift Card*). Don't just put generic terms in the form."
        ),
        color=discord.Color.from_rgb(43, 45, 49)
    )
    
    # 2. If an attachment was provided, add it to the embed
    if attachment_url:
        embed.set_image(url=attachment_url)

    embed.set_footer(text="🛡️ BLOX HUB Middleman Safe & Trusted • Your safety is our responsibility.")
    
    # 3. Send the embed along with your view and delete the original command message if desired
    await ctx.send(embed=embed, view=MMOpenView())
    
    try:
        await ctx.message.delete() # Optional: cleans up the '!mmpanel' command text from chat
    except discord.HTTPException:
        pass




# ==================== SUPPORT TICKET SYSTEM CLASSES ====================

class SupportSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Job Application", description="Apply for a staff position", emoji="💼", value="Job Application"),
            discord.SelectOption(label="Report Staff", description="Report a staff member for misconduct", emoji="⚠️", value="Report Staff"),
            discord.SelectOption(label="Host Giveaways", description="Inquire about hosting giveaways", emoji="🎉", value="Host Giveaways"),
            discord.SelectOption(label="Scammed", description="Report a scam or trade issue", emoji="🚨", value="Scammed"),
            discord.SelectOption(label="General Help", description="Ask general questions or get assistance", emoji="💡", value="General Help"),
        ]
        super().__init__(placeholder="Select a support category...", min_values=1, max_values=1, options=options)

    

async def callback(self, interaction: discord.Interaction):
        selected_option = self.values[0]
        await interaction.response.send_message(f"🔄 Creating your support ticket for **{selected_option}**, please wait...", ephemeral=True)

        try:
            guild = interaction.guild
            sos_role = discord.utils.find(lambda r: "sos" in r.name.lower(), guild.roles)
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            if sos_role:
                overwrites[sos_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            clean_name = selected_option.lower().replace(" ", "-")
            channel_name = f"sup-{clean_name}-{interaction.user.name}".lower()[:30]
            
            # Safely grab category configuration
            config = load_config().get(str(guild.id), {})
            category_id = config.get("ticket_category_id")
            ticket_category = guild.get_channel(category_id) if category_id else None
            
            ticket_channel = await guild.create_text_channel(
                name=channel_name, 
                overwrites=overwrites,
                category=ticket_category
            )

            embed = discord.Embed(
                title=f"SUPPORT TICKET: {selected_option}",
                description="• Support staff will review your case shortly. Please stay active.",
                color=discord.Color.from_rgb(255, 140, 0)
            )
            await ticket_channel.send(content=f"{interaction.user.mention} {sos_role.mention if sos_role else ''}", embed=embed, view=SupportTicketControlView())
            await interaction.edit_original_response(content=f"✅ Ticket created successfully: {ticket_channel.mention}")
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Error creating ticket: `{e}`")



class SupportSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(SupportSelect())

class SupportOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Support Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="open_support_select_v2")
    async def open_select(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = SupportSelectView()
        await interaction.response.send_message("Please select your support option from the menu below:", view=view, ephemeral=True)

class SupportTicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="support_close_btn_v2")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        has_sos = any("sos" in role.name.lower() for role in interaction.user.roles)
        if not has_sos and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only SOS staff or Administrators can close this support ticket.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Closing support ticket...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

@bot.command(name="supportpanel")
@commands.has_permissions(administrator=True)
async def supportpanel(ctx):
    # 1. Grab the attachment URL if the user uploaded an image, gif, or video
    attachment_url = ctx.message.attachments[0].url if ctx.message.attachments else None

    embed = discord.Embed(
        title="BLOX HUB | SUPPORT CENTER", 
        description="Click the button below to open a support ticket for general help, staff reports, job applications, or scam assistance.", 
        color=discord.Color.from_rgb(255, 140, 0)
    )
    
    # 2. If an attachment was provided, add it to the embed
    if attachment_url:
        embed.set_image(url=attachment_url)

    embed.set_footer(text="morning market Support • Here to help you.")
    
    # 3. Send the embed with your view
    await ctx.send(embed=embed, view=SupportOpenView())
    
    # Optional: Delete the user's original command message to keep chat clean
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass


# ==================== UTILITY & LOCKDOWN COMMANDS ====================

@bot.command(name="purge", aliases=["clear"])
async def purge(ctx, amount: int = 5):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need the **Moderator** role or higher to purge messages.")
        return
    if amount < 1 or amount > 100:
        await ctx.send("❌ Please specify a number between 1 and 100.")
        return
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Successfully cleared {amount} messages.", delete_after=4)

@bot.command(name="lock")
async def lock(ctx):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need the **Moderator** role or higher to lock channels.")
        return
    
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    
    embed = discord.Embed(
        title="🔒 CHANNEL LOCKED",
        description="This channel has been temporarily locked by staff. Normal members can no longer send messages.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name="unlock")
async def unlock(ctx):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need the **Moderator** role or higher to unlock channels.")
        return
    
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    
    embed = discord.Embed(
        title="🔓 CHANNEL UNLOCKED",
        description="This channel has been unlocked. Normal members can now chat again.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# ==================== AUTO-ROLE & WELCOME EVENT ====================

@bot.event
async def on_member_join(member):
    # 1. Automatically assign the Gamersberg Family role
    family_role = discord.utils.find(lambda r: "gamersberg family" in r.name.lower(), member.guild.roles)
    if family_role:
        try:
            await member.add_roles(family_role, reason="Auto-assigned Gamersberg Family role on join")
        except Exception as e:
            print(f"❌ Failed to assign family role to {member.name}: {e}")

    # 2. Automatically send a welcome message in a channel containing "welcome"
    welcome_channel = discord.utils.find(lambda c: "welcome" in c.name.lower() and isinstance(c, discord.TextChannel), member.guild.text_channels)
    if welcome_channel:
        embed = discord.Embed(
            title="👋 WELCOME TO GAMERSBERG!",
            description=f"Hey {member.mention}, welcome to the server! We are glad to have you in the family.",
            color=discord.Color.from_rgb(43, 45, 49)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{member.guild.member_count} • Enjoy your stay!")
        try:
            await welcome_channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Failed to send welcome message: {e}")

 # ==================== COMPLETE VOUCH SYSTEM ====================

VOUCH_FILE = "vouches.json"

def load_vouches():
    if os.path.exists(VOUCH_FILE):
        with open(VOUCH_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_vouches(data):
    with open(VOUCH_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def update_vouch_title(member: discord.Member, count: int):
    guild = member.guild
    
    title_roles = {
        "og": discord.utils.find(lambda r: "og middle man" in r.name.lower(), guild.roles),
        "legendary": discord.utils.find(lambda r: "legendary middle man" in r.name.lower(), guild.roles),
        "trusted": discord.utils.find(lambda r: "trusted middle man" in r.name.lower(), guild.roles)
    }

    target_role = None
    roles_to_remove = []

    if count > 800:
        target_role = title_roles["og"]
        roles_to_remove = [title_roles["legendary"], title_roles["trusted"]]
    elif count > 500:
        target_role = title_roles["legendary"]
        roles_to_remove = [title_roles["og"], title_roles["trusted"]]
    elif count > 1:
        target_role = title_roles["trusted"]
        roles_to_remove = [title_roles["og"], title_roles["legendary"]]
    else:
        roles_to_remove = [title_roles["og"], title_roles["legendary"], title_roles["trusted"]]

    try:
        for r in roles_to_remove:
            if r and r in member.roles:
                await member.remove_roles(r, reason="Vouch tier updated: removed old title role")
        
        if target_role and target_role not in member.roles:
            await member.add_roles(target_role, reason=f"Reached {count} vouches tier")
    except Exception as e:
        print(f"❌ Role update error for {member.name}: {e}")

@bot.command(name="setvouch")
async def setvouch(ctx, member: discord.Member, amount: int):
    if not has_middleman_or_above(ctx.author):
        await ctx.send("❌ You do not have permission to set vouches.")
        return

    data = load_vouches()
    data[str(member.id)] = amount
    save_vouches(data)

    await update_vouch_title(member, amount)
    await ctx.send(f"✅ Successfully set **{member.display_name}'s** vouches to **{amount}** and updated their title!")

@setvouch.error
async def setvouch_error(ctx, error):
    if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send("❌ **Invalid usage!** Please provide a valid member and a **number** for vouches. Example: `!setvouch @User 150`")

@bot.command(name="clearvouch")
async def clearvouch(ctx, member: discord.Member):
    if not has_middleman_or_above(ctx.author):
        await ctx.send("❌ You do not have permission to clear vouches.")
        return

    data = load_vouches()
    if str(member.id) in data:
        del data[str(member.id)]
        save_vouches(data)

    await update_vouch_title(member, 0)
    await ctx.send(f"🗑️ Successfully cleared all vouches for **{member.display_name}** and removed title roles.")

@bot.command(name="vouchlist")
async def vouchlist(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_vouches()
    count = data.get(str(target.id), 0)

    if count > 800:
        title_text = "OG Middle Man"
    elif count > 500:
        title_text = "Legendary Middle Man"
    elif count > 1:
        title_text = "Trusted Middle Man"
    else:
        title_text = "Middle Man Trainee"

    embed = discord.Embed(
        title=f"📜 Vouch Profile: {target.display_name}",
        description=f"**Total Vouches:** {count}\n**Middleman Rank:** `{title_text}`",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="👑 BLOX HUB secure Trading • Verified Record")
    
    await ctx.send(embed=embed)

# ==================== WARNING & UNWARN SYSTEM (WITH HIERARCHY) ====================

WARNINGS_FILE = "warnings.json"

def load_warnings():
    if os.path.exists(WARNINGS_FILE):
        with open(WARNINGS_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_warnings(data):
    with open(WARNINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

@bot.command(name="warn")
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need the **Moderator** role or higher to warn users.")
        return
    if not await check_hierarchy(ctx, member):
        return
    
    data = load_warnings()
    user_id = str(member.id)
    if user_id not in data:
        data[user_id] = []
    
    warning_entry = {"moderator": str(ctx.author), "reason": reason}
    data[user_id].append(warning_entry)
    save_warnings(data)
    
    await ctx.send(f"⚠️ {member.mention} has been warned by {ctx.author.mention}.\n**Reason:** {reason} (Total warnings: {len(data[user_id])})")

@bot.command(name="warnings", aliases=["warns"])
async def warnings(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_warnings()
    user_id = str(target.id)
    
    user_warns = data.get(user_id, [])
    if not user_warns:
        await ctx.send(f"✅ **{target.display_name}** has no active warnings.")
        return
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {target.display_name}",
        color=discord.Color.orange()
    )
    for idx, w in enumerate(user_warns, 1):
        embed.add_field(name=f"Warning #{idx}", value=f"**Reason:** {w['reason']}\n**Moderator:** {w['moderator']}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name="unwarn")
async def unwarn(ctx, member: discord.Member, index: int = None):
    if not has_moderator_or_above(ctx.author):
        await ctx.send("❌ You need the **Moderator** role or higher to remove warnings.")
        return
    if not await check_hierarchy(ctx, member):
        return
    
    data = load_warnings()
    user_id = str(member.id)
    
    if user_id not in data or not data[user_id]:
        await ctx.send(f"❌ **{member.display_name}** has no warnings to remove.")
        return
    
    if index is None:
        removed = data[user_id].pop()
        save_warnings(data)
        await ctx.send(f"✅ Removed the latest warning for **{member.display_name}** (`{removed['reason']}`).")
    else:
        if 1 <= index <= len(data[user_id]):
            removed = data[user_id].pop(index - 1)
            save_warnings(data)
            await ctx.send(f"✅ Removed warning #{index} for **{member.display_name}** (`{removed['reason']}`).")
        else:
            await ctx.send(f"❌ Invalid warning index! Choose between 1 and {len(data[user_id])}.")



# ==================== WALLET & GB COIN SYSTEM ====================

WALLET_FILE = "wallets.json"

def load_wallets():
    if os.path.exists(WALLET_FILE):
        with open(WALLET_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_wallets(data):
    with open(WALLET_FILE, "w") as f:
        json.dump(data, f, indent=4)

def is_owner_check(ctx):
    if ctx.author.id == ctx.guild.owner_id:
        return True
    return any(any(x in r.name.lower() for x in ["owner", "founder"]) for r in ctx.author.roles)

# --- Views for Panels ---

class WalletView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Earn Coin", style=discord.ButtonStyle.success, emoji="🪙", custom_id="wallet_earn")
    async def earn_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🪙 **How to Earn GB Coins:**\n\n"
            "• 🤝 **Trades & Middleman:** Complete successful trades or provide verified middleman services.\n"
            "• 👑 **Owner Appreciation:** Active helpers and community members can be manually rewarded by the owner.\n"
            "• 📨 **Invites:** Invite friends to the server! Every valid member you invite automatically rewards you with **+1 GB Coin**!",
            ephemeral=True
        )

    @discord.ui.button(label="Balance", style=discord.ButtonStyle.primary, emoji="👛", custom_id="wallet_balance")
    async def balance_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_wallets()
        coins = data.get(str(interaction.user.id), 0)
        await interaction.response.send_message(
            f"👛 **Purse Balance:** You currently have **{coins} GB Coins**!",
            ephemeral=True
        )

class RedeemView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Redeem Ticket", style=discord.ButtonStyle.danger, emoji="🎫", custom_id="redeem_ticket")
    async def redeem_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check user wallet balance first
        data = load_wallets()
        coins = data.get(str(interaction.user.id), 0)

        if coins < 10:
            await interaction.response.send_message(
                "❌ You do not have enough coins to redeem anything yet! First earn 10 coins at least and open a ticket.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        user = interaction.user

        owner_roles = [r for r in guild.roles if any(x in r.name.lower() for x in ["owner", "co-owner", "founder"])]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        for r in owner_roles:
            overwrites[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = discord.utils.get(guild.categories, name="Redeem Tickets") or await guild.create_category("Redeem Tickets")
        channel = await guild.create_text_channel(f"redeem-{user.name}", category=category, overwrites=overwrites)

        ping_text = " ".join([r.mention for r in owner_roles])
        await channel.send(f"🎫 {user.mention} opened a redeem ticket! {ping_text}\nState the item you want to claim from the store and make sure your balance is ready.")
        await interaction.response.send_message(f"✅ Created your redeem ticket: {channel.mention}", ephemeral=True)
        

# --- Owner Currency Commands ---

@bot.command(name="gcoin")
async def gcoin(ctx, member: discord.Member, amount: int):
    if not is_owner_check(ctx):
        await ctx.send("❌ Only the Owner/Founder can use this command.")
        return
    if amount <= 0:
        await ctx.send("❌ Amount must be greater than 0.")
        return

    data = load_wallets()
    uid = str(member.id)
    data[uid] = data.get(uid, 0) + amount
    save_wallets(data)
    await ctx.send(f"✅ Added **{amount} GB Coins** to {member.mention}'s wallet! Total: **{data[uid]}**")

@bot.command(name="subcoin", aliases=["-gcoin"])
async def subcoin(ctx, member: discord.Member, amount: int):
    if not is_owner_check(ctx):
        await ctx.send("❌ Only the Owner/Founder can use this command.")
        return
    if amount <= 0:
        await ctx.send("❌ Amount must be greater than 0.")
        return

    data = load_wallets()
    uid = str(member.id)
    current = data.get(uid, 0)
    data[uid] = max(0, current - amount)
    save_wallets(data)
    await ctx.send(f"📉 Removed **{amount} GB Coins** from {member.mention}'s wallet! Total: **{data[uid]}**")

@bot.command(name="seecoin")
async def seecoin(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = load_wallets()
    coins = data.get(str(target.id), 0)
    await ctx.send(f"👛 **{target.display_name}'s Wallet Balance:** `{coins} GB Coins`")


# --- Panel Setup Commands (Run once in your setup channels) ---

@bot.command(name="setupwallet")
async def setupwallet(ctx):
    if not is_owner_check(ctx):
        return
    embed = discord.Embed(
        title="🪙 Gamersberg Wallet & Coin Hub",
        description="Click **Earn Coin** to see how to collect GB Coins, or check your **Balance** with the purse button below!",
        color=discord.Color.gold()
    )
    embed.set_footer(text="👑 Gamersberg Secure Economy")
    await ctx.send(embed=embed, view=WalletView())

@bot.command(name="setupredeem")
async def setupredeem(ctx):
    if not is_owner_check(ctx):
        return
    embed = discord.Embed(
        title="🎁 Gamersberg Reward & Gamepass Store",
        description=(
            "Redeem your hard-earned **GB Coins** for exclusive items below!\n\n"
            "💎 **10 coins** — Random Legendary\n"
            "🐅 **25 coins** — Yeti / Tiger / Control\n"
            "🦊 **50 coins** — Kitsune Fruit\n"
            "🎨 **75 coins** — Random Skins\n"
            "🦄 **100 coins** — Random Mythicals\n"
            "🐉 **200 coins** — Dragon East / West\n"
            "🔥 **500 coins** — Ember Dragon\n"
            "🌟 **550 coins** — Perm Dragon\n"
            "🚀 **1000 coins** — Galaxy Emperian Kit\n\n"
            "*Click the button below to open a private ticket with the owners to claim your reward!*"
        ),
        color=discord.Color.purple()
    )
    embed.set_footer(text="👑 Gamersberg Secure Store")
    await ctx.send(embed=embed, view=RedeemView())


# --- Automatic Invite Tracker (+1 Coin) ---

invite_cache = {}

@bot.event
async def on_ready_invites():
    await bot.wait_until_ready()
    for guild in bot.guilds:
        try:
            invite_cache[guild.id] = await guild.invites()
        except:
            pass

@bot.event
async def on_member_join(member):
    guild = member.guild
    try:
        old_invites = invite_cache.get(guild.id, [])
        new_invites = await guild.invites()
        invite_cache[guild.id] = new_invites

        for new_inv in new_invites:
            for old_inv in old_invites:
                if new_inv.code == old_inv.code and new_inv.uses > old_inv.uses:
                    inviter = new_inv.inviter
                    if inviter and not inviter.bot:
                        data = load_wallets()
                        uid = str(inviter.id)
                        data[uid] = data.get(uid, 0) + 1
                        save_wallets(data)
                    return
    except Exception as e:
        print(f"Invite tracking error: {e}")



# Ensure a folder exists to store uploaded videos locally
os.makedirs("videos", exist_ok=True)


def load_songs():
  if not os.path.exists("songs.json"):
    return {}
  try:
    with open("songs.json", "r") as f:
      return json.load(f)
  except:
    return {}


def save_songs(songs):
  with open("songs.json", "w") as f:
    json.dump(songs, f, indent=4)


def load_wallets():
  if not os.path.exists("wallets.json"):
    return {}
  try:
    with open("wallets.json", "r") as f:
      return json.load(f)
  except:
    return {}


def save_wallets(wallets):
  with open("wallets.json", "w") as f:
    json.dump(wallets, f, indent=4)


# --- Dropdown Menu (Fixed to prevent freezing) ---
class NativeVideoSelect(discord.ui.Select):

  def __init__(self):
    songs = load_songs()
    options = []

    if not songs:
      options.append(
          discord.SelectOption(
              label="No videos uploaded yet!",
              value="none",
              description="Ask the owner to add videos using !addvideo",
          )
      )
    else:
      for name, filepath in songs.items():
        options.append(
            discord.SelectOption(
                label=name[:100],
                value=filepath,
                description="Click to load direct video quest!",
            )
        )

    super().__init__(
        placeholder="🎬 Choose a video to watch & earn...",
        min_values=1,
        max_values=1,
        options=options,
    )

  async def callback(self, interaction: discord.Interaction):
    if self.values[0] == "none":
      await interaction.response.send_message(
          "❌ No videos are available yet!", ephemeral=True
      )
      return

    filepath = self.values[0]
    if not os.path.exists(filepath):
      await interaction.response.send_message(
          "❌ Error: Video file not found on the server!", ephemeral=True
      )
      return

    # Defer response instantly so the dropdown never gets stuck or shows "interaction failed"
    await interaction.response.defer(ephemeral=True)

    # Send the actual video file directly so it plays natively inside Discord
    file = discord.File(filepath)
    view = NativeClaimView()
    await interaction.followup.send(
        content=(
            "🎥 **Here is your video!** You can play/pause directly inside"
            " Discord below.\n\nOnce you are done watching, click the button to"
            " claim your **1 GB Coin**:"
        ),
        file=file,
        view=view,
        ephemeral=True,
    )


# --- Claim Reward Button ---
class NativeClaimView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="🎁 Claim 1 GB Coin", style=discord.ButtonStyle.green
  )
  async def claim_reward(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    user_id = str(interaction.user.id)
    wallets = load_wallets()

    # Add 1 coin
    wallets[user_id] = wallets.get(user_id, 0) + 1
    save_wallets(wallets)

    button.disabled = True
    button.label = "Claimed! ✅"

    try:
      await interaction.response.edit_message(view=self)
      await interaction.followup.send(
          f"🎉 Success! You earned **1 GB Coin**. Your new balance is"
          f" **{wallets[user_id]} GB Coin(s)**!",
          ephemeral=True,
      )
    except Exception:
      await interaction.response.send_message(
          f"🎉 Success! You earned **1 GB Coin**. Your new balance is"
          f" **{wallets[user_id]} GB Coin(s)**!",
          ephemeral=True,
      )


class QuestPanelView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)
    self.add_item(NativeVideoSelect())


# --- Owner Commands ---


# 1. Add video by typing name AND attaching the video file (.mp4) to the message
@bot.command(name="addvideo")
@commands.has_permissions(administrator=True)
async def addvideo(ctx, *, name: str):
  if not ctx.message.attachments:
    await ctx.send(
        "❌ Please **attach an MP4 video file** to your message when typing"
        " `!addvideo Your Video Name`!"
    )
    return

  attachment = ctx.message.attachments[0]
  if not attachment.filename.lower().endswith((".mp4", ".mov", ".webm")):
    await ctx.send(
        "❌ Invalid file type. Please attach an MP4 video file!", ephemeral=True
    )
    return

  # Save the video file securely into the bot's folder
  filename = f"{abs(hash(name))}_{attachment.filename}"
  filepath = os.path.join("videos", filename)
  await attachment.save(filepath)

  songs = load_songs()
  songs[name] = filepath
  save_songs(songs)

  await ctx.send(
      f"✅ Successfully added video **{name}**! It is now ready in the quest"
      " dropdown."
  )


# 2. Post the quest panel
@bot.command(name="questpanel")
@commands.has_permissions(administrator=True)
async def questpanel(ctx):
  embed = discord.Embed(
      title="🎬 Direct Video Quest Center",
      description=(
          "Select a video from the dropdown menu below. It will play directly"
          " inside Discord with full play/pause controls—no YouTube links!\n\nWatch"
          " the video, then click the button to get your **1 GB Coin** reward."
      ),
      color=discord.Color.green(),
  )
  view = QuestPanelView()
  await ctx.send(embed=embed, view=view)




# --- Helper Functions for Custom Commands ---
def load_custom_cmds():
  if not os.path.exists("custom_commands.json"):
    return {}
  try:
    with open("custom_commands.json", "r") as f:
      return json.load(f)
  except:
    return {}


def save_custom_cmds(cmds):
  with open("custom_commands.json", "w") as f:
    json.dump(cmds, f, indent=4)


# --- Custom Command Management Commands ---


# 1. Add or Update a Custom Command
@bot.command(name="addcmd")
@commands.has_permissions(administrator=True)
async def addcmd(ctx, cmd_name: str, *, output_text: str):
  cmd_name = cmd_name.lower().lstrip("!")
  cmds = load_custom_cmds()
  cmds[cmd_name] = output_text
  save_custom_cmds(cmds)
  await ctx.send(f"✅ Successfully created custom command: `!{cmd_name}`!")


@addcmd.error
async def addcmd_error(ctx, error):
  if isinstance(error, commands.MissingPermissions):
    await ctx.send(
        "❌ You need Administrator permissions to create custom commands."
    )
  else:
    await ctx.send(
        "❌ Usage: `!addcmd commandname Your output message goes here`"
    )


# 2. Delete a Custom Command
@bot.command(name="delcmd")
@commands.has_permissions(administrator=True)
async def delcmd(ctx, cmd_name: str):
  cmd_name = cmd_name.lower().lstrip("!")
  cmds = load_custom_cmds()
  if cmd_name in cmds:
    del cmds[cmd_name]
    save_custom_cmds(cmds)
    await ctx.send(f"✅ Successfully deleted custom command `!{cmd_name}`!")
  else:
    await ctx.send(f"❌ Custom command `!{cmd_name}` does not exist.")


# 3. List All Custom Commands
@bot.command(name="listcmds")
async def listcmds(ctx):
  cmds = load_custom_cmds()
  if not cmds:
    await ctx.send("📁 No custom commands have been created yet.")
    return

  cmd_list = ", ".join([f"`!{c}`" for c in cmds.keys()])
  embed = discord.Embed(
      title="📜 Custom Server Commands",
      description=cmd_list,
      color=discord.Color.blue(),
  )
  await ctx.send(embed=embed)


# --- Automatic Custom Command Listener ---
@bot.event
async def on_message(message):
  # Always process built-in commands first (!addvideo, !questpanel, !addcmd, etc.)
  await bot.process_commands(message)

  if message.author.bot:
    return

  # Check if a message is a custom command
  if message.content.startswith("!"):
    parts = message.content[1:].split(" ", 1)
    cmd_name = parts[0].lower()

    cmds = load_custom_cmds()
    if cmd_name in cmds:
      # Send the exact output text saved for this command safely
      await message.channel.send(cmds[cmd_name])



#log tardes

STATS_FILE = "trade_stats.json"
CONFIG_FILE = "config.json"


def load_stats():
  if not os.path.exists(STATS_FILE):
    return {}
  try:
    with open(STATS_FILE, "r") as f:
      return json.load(f)
  except:
    return {}


def save_stats(stats):
  with open(STATS_FILE, "w") as f:
    json.dump(stats, f, indent=4)


def load_config():
  if not os.path.exists(CONFIG_FILE):
    return {}
  try:
    with open(CONFIG_FILE, "r") as f:
      return json.load(f)
  except:
    return {}


def save_config(config):
  with open(CONFIG_FILE, "w") as f:
    json.dump(config, f, indent=4)


def add_trade_count(user_id, role_type):
  stats = load_stats()
  uid = str(user_id)
  if uid not in stats:
    stats[uid] = {"client_trades": 0, "mm_trades": 0}

  key = role_type if role_type.endswith("_trades") else f"{role_type}_trades"
  if key in stats[uid]:
    stats[uid][key] += 1
  save_stats(stats)


async def get_or_create_log_channel(guild: discord.Guild):
  config = load_config()
  channel_id = config.get("log_channel_id")

  if channel_id:
    channel = guild.get_channel(channel_id)
    if channel:
      return channel

  for channel in guild.text_channels:
    if channel.name == "trade-logs":
      config["log_channel_id"] = channel.id
      save_config(config)
      return channel

  try:
    new_channel = await guild.create_text_channel(
        name="trade-logs",
        topic=(
            "Permanent log channel for completed middleman trades and proofs."
        ),
    )
    config["log_channel_id"] = new_channel.id
    save_config(config)
    return new_channel
  except Exception as e:
    print(f"Error creating log channel: {e}")
    return None


@bot.command(name="log")
async def log_trade(
    ctx, hunter: discord.Member, middleman: discord.Member, fee_option: str, *, details: str
):
  # 1. Role Check
  has_mm_role = any(
      "mm" in role.name.lower() or "middleman" in role.name.lower()
      for role in ctx.author.roles
  )
  if not has_mm_role and not ctx.author.guild_permissions.administrator:
    err_msg = await ctx.send(
        "❌ **Error:** You do not have the **MM** role required to use this"
        " command."
    )
    await asyncio.sleep(10)
    try:
      await ctx.message.delete()
      await err_msg.delete()
    except:
      pass
    return

  # 2. Attachment Check (Must have at least 2 images attached)
  if len(ctx.message.attachments) < 2:
    err_msg = await ctx.send(
        f"❌ **Error:** You attached {len(ctx.message.attachments)} image(s)."
        " Please attach exactly **2 screenshots** to your `!log` message!"
    )
    await asyncio.sleep(10)
    try:
      await ctx.message.delete()
      await err_msg.delete()
    except:
      pass
    return

  try:
    # Convert attachments into files so they upload permanently to the log channel
    file1 = await ctx.message.attachments[0].to_file()
    file2 = await ctx.message.attachments[1].to_file()

    # Update stats safely
    add_trade_count(hunter.id, "client_trades")
    add_trade_count(middleman.id, "mm_trades")

    # Build Log Embed using the safe attached file
    embed = discord.Embed(
        title="📊 New Trade Log Record", color=discord.Color.gold()
    )
    embed.add_field(
        name="👤 Hunter / Client", value=hunter.mention, inline=True
    )
    embed.add_field(
        name="🛡️ Middleman", value=middleman.mention, inline=True
    )
    embed.add_field(name="💰 Fees Given", value=fee_option, inline=True)
    embed.add_field(name="📌 Status / Details", value=details, inline=False)
    embed.set_image(url=f"attachment://{file1.filename}")
    embed.set_footer(text=f"Logged by MM: {ctx.author.display_name}")

    # Send to permanent log channel with the files attached
    log_channel = await get_or_create_log_channel(ctx.guild)
    if log_channel:
      await log_channel.send(
          content=f"🔔 **Trade Completed!** Record for {hunter.mention}",
          embed=embed,
          file=file1,
      )
      await log_channel.send(
          content=f"📸 **Secondary Proof (Join/Ban):**", file=file2
      )
    else:
      err_msg = await ctx.send(
          "⚠️️ Warning: Could not find or create the `trade-logs` channel!"
      )
      await asyncio.sleep(10)
      try:
        await ctx.message.delete()
        await err_msg.delete()
      except:
        pass
      return

    # Send success message
    success_msg = await ctx.send(
        "✅ **Trade successfully logged and stats updated!**"
    )

    # Wait 10 seconds, then auto-delete the command message and success message
    await asyncio.sleep(10)
    try:
      await ctx.message.delete()
      await success_msg.delete()
    except Exception:
      pass

  except Exception as e:
    err_msg = await ctx.send(f"❌ An unexpected error occurred: `{e}`")
    await asyncio.sleep(10)
    try:
      await ctx.message.delete()
      await err_msg.delete()
    except:
      pass


@log_trade.error
async def log_trade_error(ctx, error):
  if isinstance(error, commands.MissingRequiredArgument):
    err_msg = await ctx.send(
        "❌ **Incorrect format!**\nUsage: `!log @hunter @middleman Alt He joined"
        " us` *(Plus attach 2 images)*"
    )
    await asyncio.sleep(10)
    try:
      await ctx.message.delete()
      await err_msg.delete()
    except:
      pass


@bot.command(name="status")
async def status(ctx, member: discord.Member = None):
  target = member or ctx.author
  stats = load_stats()
  uid = str(target.id)

  user_stats = stats.get(uid, {"client_trades": 0, "mm_trades": 0})

  embed = discord.Embed(
      title=f"📈 Trade Status: {target.display_name}",
      color=discord.Color.green(),
  )
  embed.add_field(
      name="🎯 Client/Hunter Trades",
      value=str(user_stats["client_trades"]),
      inline=True,
  )
  embed.add_field(
      name="🛡️ Middleman Trades", value=str(user_stats["mm_trades"]), inline=True
  )
  embed.set_thumbnail(url=target.display_avatar.url)

  await ctx.send(embed=embed, mention_author=True)
    






# Server configurations and image pool
guild_configs = {}
trade_photos = []

# Trader feedback options
TRADER_REVIEWS_1 = [
    "wow nice mm, super fast!",
    "fast and safe trade, W mm!",
    "smooth transaction, trusted!",
    "very helpful middleman, thanks!",
    "quick response, highly recommended!",
    "legit middleman, ez trade!"
]

TRADER_REVIEWS_2 = [
    "trusted and safe, thanks!",
    "great service, W!",
    "super fast mm, appreciate it!",
    "smooth trade, 10/10!",
    "very reliable middleman!",
    "clean and safe trade!"
]

# Fallback dynamic receipt generator
def generate_vouch_image(mm_name: str, client1_name: str, client2_name: str):
    img = Image.new("RGB", (600, 240), color=(24, 25, 28))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, 600, 48], fill=(88, 101, 242))
    draw.text((20, 14), "BLOX HUB — VERIFIED TRADE RECEIPT", fill=(255, 255, 255))
    draw.rectangle([0, 0, 599, 239], outline=(60, 60, 60), width=2)

    trade_id = f"#VM-{random.randint(10000, 99999)}"
    text_content = (
        f"Transaction ID: {trade_id}\n\n"
        f"Middleman: {mm_name}\n"
        f"Trader 1: {client1_name}\n"
        f"Trader 2: {client2_name}\n\n"
        f"Status: COMPLETED & VERIFIED 🛡️"
    )
    draw.text((20, 65), text_content, fill=(220, 220, 220))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


class VouchSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.selected_channel = None
        self.selected_mm_role = None
        self.selected_client1_role = None
        self.selected_client2_role = None

        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Select Vouch Channel...",
            channel_types=[discord.ChannelType.text],
            row=0
        )
        self.mm_role_select = discord.ui.RoleSelect(
            placeholder="Select Middleman Role...",
            row=1
        )
        self.client1_role_select = discord.ui.RoleSelect(
            placeholder="Select Trader 1 Role...",
            row=2
        )
        self.client2_role_select = discord.ui.RoleSelect(
            placeholder="Select Trader 2 Role...",
            row=3
        )

        self.channel_select.callback = self.on_channel_select
        self.mm_role_select.callback = self.on_mm_select
        self.client1_role_select.callback = self.on_client1_select
        self.client2_role_select.callback = self.on_client2_select

        self.add_item(self.channel_select)
        self.add_item(self.mm_role_select)
        self.add_item(self.client1_role_select)
        self.add_item(self.client2_role_select)

    async def on_channel_select(self, interaction: discord.Interaction):
        self.selected_channel = self.channel_select.values[0]
        await interaction.response.send_message(f"✅ Channel set to {self.selected_channel.mention}", ephemeral=True)

    async def on_mm_select(self, interaction: discord.Interaction):
        self.selected_mm_role = self.mm_role_select.values[0]
        await interaction.response.send_message(f"✅ Middleman Role set to {self.selected_mm_role.mention}", ephemeral=True)

    async def on_client1_select(self, interaction: discord.Interaction):
        self.selected_client1_role = self.client1_role_select.values[0]
        await interaction.response.send_message(f"✅ Trader 1 Role set to {self.selected_client1_role.mention}", ephemeral=True)

    async def on_client2_select(self, interaction: discord.Interaction):
        self.selected_client2_role = self.client2_role_select.values[0]
        await interaction.response.send_message(f"✅ Trader 2 Role set to {self.selected_client2_role.mention}", ephemeral=True)

    @discord.ui.button(label="Save & Start (10 Min Loop)", style=discord.ButtonStyle.green, row=4)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (self.selected_channel and self.selected_mm_role and self.selected_client1_role and self.selected_client2_role):
            await interaction.response.send_message("❌ Select channel and all three roles first!", ephemeral=True)
            return

        guild_configs[interaction.guild.id] = {
            "channel_id": self.selected_channel.id,
            "mm_role_id": self.selected_mm_role.id,
            "client1_role_id": self.selected_client1_role.id,
            "client2_role_id": self.selected_client2_role.id
        }

        if not auto_vouch_loop.is_running():
            auto_vouch_loop.start()

        await interaction.response.send_message(
            f"🚀 **Auto Vouch System Activated!**\n"
            f"• **Channel:** {self.selected_channel.mention}\n"
            f"• **Middleman Role:** {self.selected_mm_role.mention}\n"
            f"• **Interval:** 1 vouch every 10 minutes",
            ephemeral=False
)


# ==========================================
# 10-MINUTE BACKGROUND TASK LOOP
# ==========================================
@tasks.loop(minutes=10)
async def auto_vouch_loop():
    for guild_id, config in guild_configs.items():
        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        channel = guild.get_channel(config["channel_id"])
        mm_role = guild.get_role(config["mm_role_id"])
        client1_role = guild.get_role(config["client1_role_id"])
        client2_role = guild.get_role(config["client2_role_id"])

        if not (channel and mm_role and client1_role and client2_role):
            continue

        middlemen = [m for m in mm_role.members if not m.bot]
        traders1 = [m for m in client1_role.members if not m.bot]
        traders2 = [m for m in client2_role.members if not m.bot]

        if not middlemen or not traders1 or not traders2:
            continue

        random_mm = random.choice(middlemen)
        random_t1 = random.choice(traders1)
        random_t2 = random.choice(traders2)
        review_1 = random.choice(TRADER_REVIEWS_1)
        review_2 = random.choice(TRADER_REVIEWS_2)

        vouch_msg = (
            f"✅ **Trade Completed Successfully!**\n"
            f"• **Middleman:** {random_mm.mention}\n"
            f"• **Trader 1:** {random_t1.mention} — *\"{review_1}\"*\n"
            f"• **Trader 2:** {random_t2.mention} — *\"{review_2}\"*\n"
            f"• **Status:** Verified & Safe Trade 🛡️"
        )

        if trade_photos:
            selected_photo = random.choice(trade_photos)
            embed = discord.Embed(color=discord.Color.green())
            embed.set_image(url=selected_photo)
            await channel.send(content=vouch_msg, embed=embed)
        else:
            img_buffer = generate_vouch_image(
                mm_name=random_mm.display_name,
                client1_name=random_t1.display_name,
                client2_name=random_t2.display_name
            )
            file = discord.File(fp=img_buffer, filename="trade_proof.png")
            await channel.send(content=vouch_msg, file=file)


@auto_vouch_loop.before_loop
async def before_vouch_loop():
    await bot.wait_until_ready()


# ==========================================
# COMMANDS & EVENTS
# ==========================================
@bot.command(name="addlog")
@commands.has_permissions(administrator=True)
async def addlog(ctx):
    if not ctx.message.attachments:
        await ctx.send("❌ Please attach one or more trade images when running `!addlog`!")
        return

    added_count = 0
    for attachment in ctx.message.attachments:
        if any(attachment.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
            trade_photos.append(attachment.url)
            added_count += 1

    await ctx.send(f"✅ Successfully added **{added_count}** trade proof photo(s)! Total pool photos: **{len(trade_photos)}**.")


@bot.command(name="setup_vouch")
@commands.has_permissions(administrator=True)
async def setup_vouch(ctx):
    embed = discord.Embed(
        title="⚙️ Auto Vouch Setup Panel",
        description="Select your vouch channel, Middleman role, and both Trader roles below.",
        color=discord.Color.blue()
    )
    view = VouchSetupView()
    await ctx.send(embed=embed, view=view)



@bot.event
async def on_message(message):
    # ... your middleman or ticket event code ...

    await bot.process_commands(message)  # <--- WITHOUT THIS, standard commands WILL NOT WORK



# 1. Dropdown view for selecting the role
class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180) # View times out after 3 minutes

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select a role to mass-DM...",
        min_values=1,
        max_values=1
    )
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        selected_role = select.values[0]
        # Open the modal, passing the selected role ID
        await interaction.response.send_modal(SnitchModal(role_id=selected_role.id))

# 2. Modal for typing the message/link
class SnitchModal(discord.ui.Modal, title="Configure Auto-DM Message"):
    message_input = discord.ui.TextInput(
        label="Message to send (Links allowed)",
        style=discord.TextStyle.paragraph,
        placeholder="Type your message or invite link here...",
        required=True
    )

    def __init__(self, role_id: int):
        super().__init__()
        self.role_id = role_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        role = guild.get_role(self.role_id)

        if not role:
            return await interaction.edit_original_response(content="❌ Role not found.")

        # Ensure all members are fetched/cached
        await guild.chunk()

        custom_message = self.message_input.value
        success_count = 0
        fail_count = 0

        # Loop through non-bot members in the role
        for member in role.members:
            if member.bot:
                continue
            try:
                await member.send(f"📢 **Announcement from {guild.name}**\n\n{custom_message}")
                success_count += 1
                # 1-second delay to prevent hitting Discord rate limits / spam filters
                await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=1)) # or asyncio.sleep(1)
            except Exception:
                fail_count += 1 # User has DMs closed or blocked the bot

        # Completion summary message
        await interaction.edit_original_response(
            content=f"✅ **SnitchAuto Completed!**\n"
                    f"- Target Role: @{role.name}\n"
                    f"- Successfully Sent: {success_count}\n"
                    f"- Failed (Closed DMs): {fail_count}"
        )

# 3. The Prefix Command (!snitchauto)
# (Assuming you are using commands.Bot with command_prefix='!')
@bot.command(name="snitchauto")
@commands.has_permissions(administrator=True)
async def snitchauto(ctx):
    embed = discord.Embed(
        title="🚨 SnitchAuto Panel",
        description="Select a role from the dropdown below. Once selected, a window will pop up asking for the message you want to send.",
        color=0xFF0000
    )
    view = RoleSelectView()
    await ctx.send(embed=embed, view=view)

@snitchauto.error
async def snitchauto_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You do not have permission to use this command.")




# Dictionary to store raid channels per server (guild_id -> list of channel_ids)
raid_channels = {}

# Dictionary to store backed-up channel overwrites for !fnuke (guild_id -> {channel_id: {target: overwrite}})
nuke_backups = {}

# ==========================================
# 1. RAID SETUP COMMAND & MULTI-SELECT VIEW
# ==========================================

class ChannelSelectView(discord.ui.View):
    def __init__(self, guild_channels):
        super().__init__(timeout=180)
        
        # Discord ChannelSelect allows picking multiple text/voice channels
        select = discord.ui.ChannelSelect(
            placeholder="Select channels to hide during a raid...",
            min_values=1,
            max_values=min(len(guild_channels), 25), # Max 25 per select dropdown
            channel_types=[discord.ChannelType.text, discord.ChannelType.voice]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_channels = self.children[0].values
        guild_id = interaction.guild.id
        
        # Save channel IDs
        raid_channels[guild_id] = [ch.id for ch in selected_channels]
        
        channel_mentions = ", ".join([ch.mention for ch in selected_channels])
        
        await interaction.response.send_message(
            f"✅ **Raid Setup Saved!**\nTarget channels ({len(selected_channels)}): {channel_mentions}",
            ephemeral=True
        )


@bot.command(name="raidsetup")
@commands.has_permissions(administrator=True)
async def raidsetup(ctx):
    """Opens a dropdown to select channels to hide during a raid."""
    text_and_voice = [ch for ch in ctx.guild.channels if isinstance(ch, (discord.TextChannel, discord.VoiceChannel))]
    
    if not text_and_voice:
        return await ctx.send("❌ No text or voice channels found in this server.")

    embed = discord.Embed(
        title="🛡️ Raid Setup Panel",
        description="Choose all the channels from the dropdown below that should be hidden when `!raidalert` is activated.",
        color=0x3498DB
    )
    
    view = ChannelSelectView(text_and_voice)
    await ctx.send(embed=embed, view=view)


# ==========================================
# 2. RAID ALERT COMMAND
# ==========================================

@bot.command(name="raidalert")
@commands.has_permissions(administrator=True)
async def raidalert(ctx):
    """Immediately hides all pre-selected raid channels from @everyone."""
    guild_id = ctx.guild.id
    target_ids = raid_channels.get(guild_id, [])

    if not target_ids:
        return await ctx.send("❌ No channels configured! Please run `!raidsetup` first.")

    hidden_count = 0
    everyone_role = ctx.guild.default_role

    async with ctx.typing():
        for ch_id in target_ids:
            channel = ctx.guild.get_channel(ch_id)
            if channel:
                # Deny View Channel for @everyone
                await channel.set_permissions(everyone_role, view_channel=False, reason="Raid Alert Activated")
                hidden_count += 1

    await ctx.send(f"🚨 **RAID ALERT ACTIVATED!**\nHidden **{hidden_count}** channel(s) from `@everyone`.")


# ==========================================
# 3. UNRAID ALERT COMMAND
# ==========================================

@bot.command(name="unraidalert")
@commands.has_permissions(administrator=True)
async def unraidalert(ctx):
    """Restores visibility for all configured raid channels."""
    guild_id = ctx.guild.id
    target_ids = raid_channels.get(guild_id, [])

    if not target_ids:
        return await ctx.send("❌ No channels configured! Run `!raidsetup` first.")

    restored_count = 0
    everyone_role = ctx.guild.default_role

    async with ctx.typing():
        for ch_id in target_ids:
            channel = ctx.guild.get_channel(ch_id)
            if channel:
                # Reset or grant View Channel for @everyone
                await channel.set_permissions(everyone_role, view_channel=True, reason="Unraid Alert Deactivated")
                restored_count += 1

    await ctx.send(f"🟢 **Raid Alert Deactivated.**\nRestored visibility for **{restored_count}** channel(s).")


# ==========================================
# 4. FAKE NUKE COMMAND (!fnuke)
# ==========================================

@bot.command(name="fnuke")
@commands.has_permissions(administrator=True)
async def fnuke(ctx):
    """Hides ALL channels from everyone and disables other bots."""
    guild = ctx.guild
    guild_id = guild.id
    
    # Store current overwrites so !wnuke can undo them perfectly
    nuke_backups[guild_id] = {}
    
    everyone_role = guild.default_role
    bot_member = guild.me

    async with ctx.typing():
        for channel in guild.channels:
            # Backup existing overwrites
            nuke_backups[guild_id][channel.id] = dict(channel.overwrites)

            # Start fresh overwrites dictionary
            new_overwrites = channel.overwrites

            # 1. Hide from @everyone
            everyone_overwrite = new_overwrites.get(everyone_role, discord.PermissionOverwrite())
            everyone_overwrite.view_channel = False
            everyone_overwrite.send_messages = False
            new_overwrites[everyone_role] = everyone_overwrite

            # 2. Block all other bots and roles
            for target in list(new_overwrites.keys()):
                if isinstance(target, discord.Member) and target.bot and target.id != bot_member.id:
                    bot_overwrite = new_overwrites[target]
                    bot_overwrite.view_channel = False
                    bot_overwrite.send_messages = False
                    new_overwrites[target] = bot_overwrite
                elif isinstance(target, discord.Role) and target.is_bot_managed():
                    bot_role_overwrite = new_overwrites[target]
                    bot_role_overwrite.view_channel = False
                    bot_role_overwrite.send_messages = False
                    new_overwrites[target] = bot_role_overwrite

            # Apply updated channel permissions
            try:
                await channel.edit(overwrites=new_overwrites, reason="Fake Nuke Activated")
            except Exception:
                pass

    await ctx.send("☢️ **FNUKE ACTIVATED!** All channels hidden and other bots disabled. Use `!wnuke` to revert.")


# ==========================================
# 5. WITHDRAW NUKE COMMAND (!wnuke)
# ==========================================

@bot.command(name="wnuke")
@commands.has_permissions(administrator=True)
async def wnuke(ctx):
    """Restores all channels and permissions to their state prior to !fnuke."""
    guild_id = ctx.guild.id
    
    if guild_id not in nuke_backups or not nuke_backups[guild_id]:
        return await ctx.send("❌ No active `!fnuke` state found to revert.")

    backup = nuke_backups[guild_id]

    async with ctx.typing():
        for channel_id, saved_overwrites in backup.items():
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                try:
                    # Restore original channel overwrites exact state
                    await channel.edit(overwrites=saved_overwrites, reason="Fnuke Reverted via Wnuke")
                except Exception:
                    pass

    # Clear backup memory for this guild
    del nuke_backups[guild_id]

    await ctx.send("🔄 **WNUKE COMPLETED!** All channel permissions and bot privileges have been restored.")




# Storage for guild configurations (guild_id -> dict)
# Save this to a JSON file or database to keep settings across bot restarts!
support_configs = {}

# Keywords for Emergency Escalation
SCAM_KEYWORDS = ["scam", "scammed", "staff betrayal", "betrayal", "stole", "hacked"]

# Keywords for Rule Violation / Cross-Trade Detection
VIOLATION_KEYWORDS = ["mm", "middleman", "cross trade", "crosstrade", "cross trading", "bad word", "scammer"]


# ==========================================
# 1. SETUP COMMAND & DROPDOWN VIEWS
# ==========================================

class SetupSupportView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=180)
        self.guild = guild
        self.target_channel = None
        self.max_assist_role = None
        self.emergency_role = None

        # 1. Select Channel Dropdown
        channel_select = discord.ui.ChannelSelect(
            placeholder="1. Choose the Support Channel...",
            channel_types=[discord.ChannelType.text],
            custom_id="select_channel"
        )
        channel_select.callback = self.channel_callback
        self.add_item(channel_select)

        # 2. Select Max Assist Role Dropdown
        max_role_select = discord.ui.RoleSelect(
            placeholder="2. Choose Maximum Assist Role...",
            custom_id="select_max_role"
        )
        max_role_select.callback = self.max_role_callback
        self.add_item(max_role_select)

        # 3. Select Emergency Role Dropdown
        emergency_role_select = discord.ui.RoleSelect(
            placeholder="3. Choose Emergency Role...",
            custom_id="select_emergency_role"
        )
        emergency_role_select.callback = self.emergency_role_callback
        self.add_item(emergency_role_select)

    async def channel_callback(self, interaction: discord.Interaction):
        self.target_channel = interaction.data["values"][0]
        await interaction.response.send_message(f"✅ Target channel selected.", ephemeral=True)

    async def max_role_callback(self, interaction: discord.Interaction):
        self.max_assist_role = interaction.data["values"][0]
        await interaction.response.send_message(f"✅ Max assist role selected.", ephemeral=True)

    async def emergency_role_callback(self, interaction: discord.Interaction):
        self.emergency_role = interaction.data["values"][0]
        await interaction.response.send_message(f"✅ Emergency role selected.", ephemeral=True)

    @discord.ui.button(label="Save Configuration & Deploy Panel", style=discord.ButtonStyle.green, row=4)
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.target_channel or not self.max_assist_role or not self.emergency_role:
            return await interaction.response.send_message("❌ Please select a channel, maximum assist role, AND emergency role before saving!", ephemeral=True)

        guild_id = interaction.guild.id
        channel = interaction.guild.get_channel(int(self.target_channel))

        # Save to configuration store
        support_configs[guild_id] = {
            "channel_id": int(self.target_channel),
            "max_assist_role_id": int(self.max_assist_role),
            "emergency_role_id": int(self.emergency_role)
        }

        # Deploy Auto Support Button Panel to the configured channel
        embed = discord.Embed(
            title="🛠️ Auto Support Center BLOX HUB",
            description="Click the button below to open a private ticket with our automated support system.",
            color=0x3498DB
        )
        panel_view = OpenTicketView()
        await channel.send(embed=embed, view=panel_view)

        await interaction.response.send_message(f"🎉 **Setup Complete!** Panel deployed to {channel.mention}.", ephemeral=True)


class OpenTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent view

    @discord.ui.button(label="📩 Request Auto Support", style=discord.ButtonStyle.primary, custom_id="open_auto_support")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        config = support_configs.get(guild.id)

        if not config:
            return await interaction.response.send_message("❌ Auto Support system is not configured yet.", ephemeral=True)

        max_role = guild.get_role(config["max_assist_role_id"])

        # Check user's highest role vs Max Assist Role
        if max_role and user.top_role >= max_role:
            return await interaction.response.send_message(
                "⚠️ **Access Denied:** You have a higher or equivalent rank. Please redirect to the executive support channel to open a ticket with an executive directly.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        # Create private ticket channel for User, Bot, and Owner
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            guild.owner: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ticket_channel = await guild.create_text_channel(
            name=f"support-{user.name}",
            overwrites=overwrites,
            reason="Auto Support Ticket Opened"
        )

        await interaction.followup.send(f"✅ Private support ticket created: {ticket_channel.mention}", ephemeral=True)

        # Step 1: Send initial greeting message in the private ticket channel
        await ticket_channel.send(f"Hello {user.mention}, I am your **Support Executive** bot! 🤖")


@bot.command(name="setupchat")
@commands.has_permissions(administrator=True)
async def setupchat(ctx):
    """Command to configure the auto support panel, roles, and channels."""
    embed = discord.Embed(
        title="⚙️ Auto Support Setup",
        description="Select the channel, maximum assist role limit, and emergency role from the options below.",
        color=0xF1C40F
    )
    view = SetupSupportView(ctx.guild)
    await ctx.send(embed=embed, view=view)


# ==========================================
# 2. AUTOMATED TICKET INTERACTION & DETECTOR
# ==========================================

# Internal state dictionary to track ticket stages
# ticket_channel_id -> {"stage": str, "offender": Member}
ticket_states = {}

@bot.event
async def on_message(message):
    # Ignore messages sent by bots
    if message.author.bot:
        return

    # Process standard commands first
    await bot.process_commands(message)

    # Check if this message is inside a support ticket channel
    if not message.channel.name.startswith("support-"):
        return

    channel = message.channel
    guild = message.guild
    config = support_configs.get(guild.id)

    if not config:
        return

    state = ticket_states.get(channel.id, {"stage": "INIT"})

    # --- STAGE 1: User sent initial message (e.g. "hi", "hello") ---
    if state["stage"] == "INIT":
        ticket_states[channel.id] = {"stage": "AWAITING_DESCRIPTION"}
        await channel.send("Please describe your issue in detail below 👇")
        return

    # --- STAGE 2: User described their issue -> Read & Analyze Message ---
    if state["stage"] == "AWAITING_DESCRIPTION":
        content_lower = message.content.lower()

        # Check Scenario A: Scam or Staff Betrayal
        if any(word in content_lower for word in SCAM_KEYWORDS):
            emergency_role = guild.get_role(config["emergency_role_id"])
            if emergency_role:
                # Add Emergency Role permissions to the ticket channel
                await channel.set_permissions(emergency_role, view_channel=True, send_messages=True)
                await channel.send(f"🚨 **Emergency Detected!** {emergency_role.mention} has been added to this ticket.\nAn executive will assist you shortly.")
            else:
                await channel.send("🚨 An executive will help you shortly.")

            ticket_states[channel.id] = {"stage": "ESCALATED"}
            return

        # Check Scenario B: Cross Trade, MM, or Bad Words Detected
        if any(word in content_lower for word in VIOLATION_KEYWORDS):
            ticket_states[channel.id] = {"stage": "AWAITING_SCREENSHOT"}
            await channel.send("🔍 **Violation Keyword Detected!** Please provide a screenshot evidence of the situation below.")
            return

        # Default fallback if no special keywords matched
        ticket_states[channel.id] = {"stage": "GENERAL"}
        await channel.send("Thank you. An executive will review your message and assist you shortly.")
        return

    # --- STAGE 3: User uploaded screenshot -> Ask for offending person ---
    if state["stage"] == "AWAITING_SCREENSHOT":
        # Check if the user attached an image or image link
        has_image = len(message.attachments) > 0 or any(ext in message.content.lower() for ext in ['.png', '.jpg', '.jpeg', '.webp'])
        
        if has_image:
            ticket_states[channel.id] = {"stage": "AWAITING_OFFENDER"}
            await channel.send("📸 **Screenshot received!** Now, please mention or enter the username/ID of the person who said/did this (e.g., `@justicemaker99`).")
        else:
            await channel.send("⚠️ Please attach a valid screenshot image to proceed.")
        return

    # --- STAGE 4: User mentions the target person -> Execute 30-min Timeout ---
    if state["stage"] == "AWAITING_OFFENDER":
        target_member = None

        # 1. Try to find explicitly mentioned user
        if message.mentions:
            target_member = message.mentions[0]
        else:
            # 2. Try parsing by username or ID
            clean_input = message.content.strip().replace("@", "")
            target_member = discord.utils.find(
                lambda m: m.name.lower() == clean_input.lower() or str(m.id) == clean_input,
                guild.members
            )

        if not target_member:
            return await channel.send("❌ Could not find that user in this server! Please mention them correctly (e.g. `@justicemaker99`).")

        # Apply 30-minute Timeout to the offender
        try:
            duration = datetime.timedelta(minutes=30)
            await target_member.timeout(duration, reason="Automated penalty issued from Auto Support ticket.")
            
            # Reset ticket state
            ticket_states[channel.id] = {"stage": "COMPLETED"}

            # Confirm punishment inside the ticket channel
            await channel.send(f"🔨 **Action Taken!** User {target_member.mention} has received a **30-minute timeout** punishment.")
        except discord.Forbidden:
            await channel.send(f"❌ Failed to timeout {target_member.mention}. The bot lacks permissions or the user has a higher role.")
        except Exception as e:
            await channel.send(f"❌ An error occurred while timing out the user: `{e}`")
        return


#single dms

@bot.command(name="dm")
@commands.has_permissions(administrator=True)
async def direct_message(ctx, target: str, *, message_content: str = ""):
    """
    Usage:
    !dm @user Check out this video https://youtube.com
    !dm everyone Big announcement!
    """
    
    # Collect attachments if uploaded with the command
    files = []
    if ctx.message.attachments:
        for attachment in ctx.message.attachments:
            file = await attachment.to_file()
            files.append(file)

    if not message_content and not files:
        return await ctx.send("❌ Please provide a message, a link, or attach a video/file.")

    # ==========================================================
    # SCENARIO A: Target is "everyone" (Lightning-Fast / Concurrent)
    # ==========================================================
    if target.lower() == "everyone":
        status_msg = await ctx.send("⚡ Sending quick mass-DM to `@everyone`...")
        
        await ctx.guild.chunk()
        members = [m for m in ctx.guild.members if not m.bot]

        # Helper function to send individual DMs concurrently
        async def send_to_member(member):
            try:
                # Re-create file references for individual DMs if attachments exist
                dm_files = [await att.to_file() for att in ctx.message.attachments] if ctx.message.attachments else []
                await member.send(content=message_content if message_content else None, files=dm_files)
                return True
            except Exception:
                return False

        # Fire all requests concurrently. discord.py automatically manages API rate limits safely.
        results = await asyncio.gather(*(send_to_member(m) for m in members))
        
        success_count = results.count(True)
        fail_count = results.count(False)

        await status_msg.edit(
            content=f"⚡ **Quick Mass DM Completed!**\n"
                    f"- Successful: `{success_count}`\n"
                    f"- Failed (DMs locked): `{fail_count}`"
        )
        return

    # ==========================================================
    # SCENARIO B: Target is a specific @User or User ID
    # ==========================================================
    if ctx.message.mentions:
        target_user = ctx.message.mentions[0]
    else:
        try:
            user_id = int(target.strip("<@!>"))
            target_user = ctx.guild.get_member(user_id) or await bot.fetch_user(user_id)
        except ValueError:
            return await ctx.send("❌ Invalid user or syntax! Use `!dm @user <msg>` or `!dm everyone <msg>`.")

    if not target_user:
        return await ctx.send("❌ User not found in this server.")

    try:
        await target_user.send(content=message_content if message_content else None, files=files)
        await ctx.send(f"✅ DM successfully sent to {target_user.mention}!")
    except discord.Forbidden:
        await ctx.send(f"❌ Could not DM {target_user.mention}. Their DMs are turned off.")
    except Exception as e:
        await ctx.send(f"❌ Error sending DM: `{e}`")

@direct_message.error
async def direct_message_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need Administrator permissions to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Incorrect usage! Example: `!dm @user hello` or `!dm everyone check this link`")




# ==========================================
# TICKET STORE CATEGORY SELECTOR SYSTEM
# ==========================================

class TicketCategorySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        
        # ChannelSelect filtering only for Categories
        self.category_select = discord.ui.ChannelSelect(
            placeholder="Select category for bot tickets...",
            channel_types=[discord.ChannelType.category],
            row=0
        )
        self.category_select.callback = self.on_category_select
        self.add_item(self.category_select)

    async def on_category_select(self, interaction: discord.Interaction):
        selected_category = self.category_select.values[0]
        
        # Ensure guild config entry exists
        if interaction.guild.id not in guild_configs:
            guild_configs[interaction.guild.id] = {}
            
        # Save the category ID
        guild_configs[interaction.guild.id]["ticket_category_id"] = selected_category.id

        await interaction.response.send_message(
            f"✅ **Ticket Store Updated!** All future bot-created tickets will now automatically open inside the category: **{selected_category.name}**.",
            ephemeral=True
        )


@bot.command(name="ticketstore")
@commands.has_permissions(administrator=True)
async def ticketstore(ctx):
    """Select the category where all future bot tickets will be created."""
    embed = discord.Embed(
        title="📁 Ticket Store Configuration",
        description="Choose the category from the dropdown menu below where you want all bot-created tickets to appear.",
        color=discord.Color.blue()
    )
    view = TicketCategorySelectView()
    await ctx.send(embed=embed, view=view)




CONFIG_FILE = "guild_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

class TicketAndStatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    # --- 1. /close choose (Set log channel) ---
    @app_commands.command(name="close-choose", description="Choose the channel where closed ticket transcripts will be logged.")
    @app_commands.describe(channel="The channel to send transcripts to")
    async def close_choose(self, interaction: discord.Interaction, channel: discord.TextChannel):
        # Optional: restrict to admin/moderator
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You need **Manage Channels** permission to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        if guild_id not in self.config:
            self.config[guild_id] = {}
        
        self.config[guild_id]["log_channel_id"] = channel.id
        save_config(self.config)

        await interaction.response.send_message(f"✅ Success! Ticket transcripts will now be sent to {channel.mention}.", ephemeral=True)

    # --- 2. /close (Close ticket, generate transcript, DM user, log) ---
    @app_commands.command(name="close", description="Closes the active ticket, DMs transcript, and logs it.")
    @app_commands.describe(reason="Reason for closing the ticket")
    async def close(self, interaction: discord.Interaction, reason: str = "No reason provided"):
        guild_id = str(interaction.guild.id)
        
        # Check if log channel is set
        log_channel_id = self.config.get(guild_id, {}).get("log_channel_id")
        if not log_channel_id:
            await interaction.response.send_message(
                "❌ Please configure a transcript channel first using `/close-choose #channel`!", ephemeral=True
            )
            return

        log_channel = interaction.guild.get_channel(log_channel_id)
        if not log_channel:
            await interaction.response.send_message("❌ The configured transcript channel no longer exists.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        channel = interaction.channel
        
        # Generate transcript from channel message history (last 500 messages)
        messages = []
        async for msg in channel.history(limit=500, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            messages.append(f"[{timestamp}] {msg.author}: {msg.content}")
        
        transcript_text = f"--- TICKET TRANSCRIPT: {channel.name} ---\nClosed by: {interaction.user}\nReason: {reason}\n\n" + "\n".join(messages)
        transcript_file = discord.File(
            fp=io.BytesIO(transcript_text.encode("utf-8")),
            filename=f"transcript-{channel.name}.txt"
        )

        # Attempt to find the ticket creator or members who participated in the ticket
        # Looking at channel permission overwrites or non-bot members who sent messages
        target_member = None
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.bot and target != interaction.guild.me:
                target_member = target
                break

        # Send DM to the ticket user if found
        if target_member:
            try:
                dm_embed = discord.Embed(
                    title="🔒 Your Ticket Has Been Closed",
                    description=f"Your ticket in **{interaction.guild.name}** has been closed.",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                await target_member.send(embed=dm_embed, file=discord.File(
                    fp=io.BytesIO(transcript_text.encode("utf-8")),
                    filename=f"transcript-{channel.name}.txt"
                ))
            except Exception:
                pass # User might have DMs closed

        # Send log to the designated log channel
        log_embed = discord.Embed(
            title="📁 Ticket Closed",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        log_embed.add_field(name="Ticket Name", value=channel.name, inline=True)
        log_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        
        await log_channel.send(embed=log_embed, file=transcript_file)

        # Notify in channel and delete after 5 seconds
        await interaction.followup.send("🔒 Ticket transcript saved and sent. Closing channel in 5 seconds...")
        import asyncio
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket closed by {interaction.user}: {reason}")
        except Exception:
            pass

    # --- 3. /w (Server members and online count) ---
    @app_commands.command(name="w", description="Shows server member count and online status.")
    async def w(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        total_members = guild.member_count
        # Count members whose status is not offline (online, idle, dnd)
        online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)
        
        embed = discord.Embed(
            title=f"📊 {guild.name} Statistics",
            color=discord.Color.blue()
        )
        embed.add_field(name="👥 Total Members", value=str(total_members), inline=True)
        embed.add_field(name="🟢 Online Members", value=str(online_members), inline=True)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(TicketAndStatsCog(bot))





# Run your bot using your bot token
# bot.run("YOUR_BOT_TOKEN")






# bot.run("YOUR_BOT_TOKEN_HERE")


                                 
        
      
            
    

bot.run(os.getenv('DISCORD_TOKEN'))

    


    



            


    
    




        




