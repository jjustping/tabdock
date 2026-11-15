"""Today's and tomorrow's events on Windows from iCalendar (.ics) files: put exported calendars (Google, Outlook,
iCloud…) into %LOCALAPPDATA%\\TabDock\\calendars\\ (or ~/.config/tabdock/calendars/). Same reader as on Linux."""
import os

from ..linux import calendar as _ics
from . import appdata

_ics.SOURCES = [os.path.join(appdata("calendars"), "*.ics"), os.path.expanduser("~/.config/tabdock/calendars/*.ics")]
CalendarFeed = _ics.CalendarFeed
read_events = _ics.read_events
