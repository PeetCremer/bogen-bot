# Getting started
- COPY the .env.example file to .env and and fill the variables DISCORD_BOT_TOKEN and CHARACTER_SHEET_URL with reasonable values
- RUN bot.py

# Changelog
## Version 0.0.1
- Load Character sheet from google docs
- Parse it as csv and store attribute value pairs in dict
- Can then roll on any attribute or combination of attributes using !check command
- Update of sheet via !update_sheet command
- Printing sheet (as dict for now) iwth !print_sheet command